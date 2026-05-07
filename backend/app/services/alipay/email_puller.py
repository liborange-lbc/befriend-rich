"""
Alipay email puller — fetch 支付宝业务凭证 emails from IMAP.

Each batch consists of up to two PDFs from the same ISO week:
1. 资产证明 (asset proof) — fund holdings（必须有）
2. 交易明细 (transaction detail) — weekly investment（可能没有）

从最新邮件向前检索，遇到已导入过的周则停止。
"""

import email
import imaplib
import logging
import tempfile
from dataclasses import dataclass, field
from datetime import date
from email.header import decode_header, make_header
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.alipay.parser import (
    compute_weekly_investments,
    parse_asset_proof,
    parse_transaction_detail,
)
from app.services.config_service import get_config_with_db
from app.services.webank.importer import (
    ImportResult,
    import_from_parsed_data,
    normalize_to_monday,
)

logger = logging.getLogger(__name__)

ALIPAY_SUBJECT = "支付宝业务凭证"
CHANNEL = "支付宝"


@dataclass
class _WeekBatch:
    """同一 ISO 周内的资产证明 + 交易明细 PDF。"""
    monday: date
    asset_proof_path: Path | None = None
    transaction_detail_path: Path | None = None
    statement_date: date | None = None
    total_amount: float = 0.0


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _classify_pdf(pdf_path: Path) -> str:
    """Classify PDF as 'asset_proof' or 'transaction_detail' by reading page 1."""
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    if "资产证明" in text:
        return "asset_proof"
    if "交易明细" in text:
        return "transaction_detail"
    return "unknown"


def _fetch_and_group_pdfs(
    email_account: str,
    password: str,
    imap_host: str,
) -> list[_WeekBatch]:
    """
    从 IMAP 拉取支付宝 PDF 附件，按 ISO 周分组。

    扫描最近 200 封邮件，提取所有支付宝 PDF 并按 ISO 周分组。
    返回按周从旧到新排列的 batch 列表。
    """
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        imaplib.Commands["ID"] = ("AUTH",)
        client_id = ("name", "Nanobot", "version", "1.0", "vendor", "Nanobot")
        client._simple_command("ID", '("' + '" "'.join(client_id) + '")')
        status, _ = client.select("INBOX")
        if status != "OK":
            raise RuntimeError("Cannot open mailbox")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        message_ids = data[0].split()
        tmp_dir = Path(tempfile.mkdtemp(prefix="alipay_"))
        batches: dict[date, _WeekBatch] = {}

        for msg_id in reversed(message_ids[-200:]):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw = fetched[0][1]
            msg = email.message_from_bytes(raw)
            subject = _decode_mime_header(msg.get("Subject"))
            if ALIPAY_SUBJECT not in subject:
                continue

            # 提取 PDF 附件
            for part in msg.walk():
                filename = part.get_filename()
                if not filename:
                    continue
                name = _decode_mime_header(filename)
                if not name.lower().endswith(".pdf"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                safe_name = name.replace("/", "_").replace("\\", "_")
                pdf_path = tmp_dir / f"msg{msg_id.decode()}_{safe_name}"
                pdf_path.write_bytes(payload)

                pdf_type = _classify_pdf(pdf_path)
                if pdf_type == "unknown":
                    continue

                if pdf_type == "asset_proof":
                    holdings, stmt_date = parse_asset_proof(pdf_path)
                    monday = normalize_to_monday(stmt_date)
                    if monday not in batches:
                        batches[monday] = _WeekBatch(monday=monday)
                    batch = batches[monday]
                    # 取最新的资产证明（从新到旧扫描，第一个即最新）
                    if not batch.asset_proof_path:
                        batch.asset_proof_path = pdf_path
                        batch.statement_date = stmt_date
                        batch.total_amount = sum(h.amount for h in holdings)

                elif pdf_type == "transaction_detail":
                    transactions = parse_transaction_detail(pdf_path)
                    if transactions:
                        latest_txn_date = max(t.trade_date for t in transactions)
                        monday = normalize_to_monday(latest_txn_date)
                        if monday not in batches:
                            batches[monday] = _WeekBatch(monday=monday)
                        if not batches[monday].transaction_detail_path:
                            batches[monday].transaction_detail_path = pdf_path

        # 按周从旧到新排列
        return [batches[k] for k in sorted(batches.keys())]
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


def pull_alipay_statements(db: Session) -> list[ImportResult]:
    """
    拉取支付宝基金对账单并导入。

    从最新邮件向前检索，按 ISO 周分组，遇到已处理过的周停止。
    每个周 batch 包含：资产证明（必须）+ 交易明细（可选）。

    Returns:
        导入结果列表（每周一个），空列表表示无新数据。
    """
    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    batches = _fetch_and_group_pdfs(imap_email, imap_password, imap_host)
    if not batches:
        logger.info("No new Alipay emails to import")
        return []

    results: list[ImportResult] = []

    for batch in batches:
        if not batch.asset_proof_path:
            logger.warning(f"Week {batch.monday}: no asset proof, skipping")
            continue

        # 解析资产证明
        holdings, statement_date = parse_asset_proof(batch.asset_proof_path)
        if not holdings:
            logger.warning(f"Week {batch.monday}: empty holdings, skipping")
            continue

        statement_date = normalize_to_monday(statement_date)

        # 解析交易明细（可选）
        weekly_investments: dict[str, float] = {}
        if batch.transaction_detail_path:
            transactions = parse_transaction_detail(batch.transaction_detail_path)
            weekly_investments = compute_weekly_investments(transactions, statement_date)
        else:
            logger.info(f"Week {batch.monday}: no transaction detail, weekly_investment=empty")

        # 构造导入数据
        items: list[dict] = []
        for h in holdings:
            items.append({
                "资产项": h.fund_name,
                "金额(元)": h.amount,
                "币种": "CNY",
                "基金代码": h.fund_code,
            })

        try:
            result = import_from_parsed_data(
                db=db,
                items=items,
                file_name=f"alipay_{statement_date.isoformat()}.pdf",
                record_date=statement_date,
                source="alipay_email",
                channel=CHANNEL,
                weekly_investments=weekly_investments,
            )
            results.append(result)
            logger.info(f"Alipay import week {batch.monday}: {result}")
        except Exception as e:
            logger.error(f"Alipay import week {batch.monday} failed: {e}")

    return results
