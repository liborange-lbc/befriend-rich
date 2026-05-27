"""
国泰海通「客户资产证明」每日邮件解析器

发件人：SecuritiesDepository@gtht.com
附件：T_0004_<账号>_<yyyyMMdd>.xlsx
每天凌晨 2-3 点发送前一交易日持仓；job 在 5:00 执行时拉取。

持仓逻辑：
- 逐只证券 + 人民币资金余额各建一条 PortfolioRecord（渠道=国泰海通）
- 文件中市值已转换为人民币，全部用 CNY 写入
- 非交易日无邮件时不报错，由 job_weekly_data_completion 递延
"""

import email
import imaplib
import logging
import re
import tempfile
from datetime import date, timedelta
from email.header import decode_header, make_header
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.config_service import get_config_with_db
from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

SENDER_KEYWORD = "SecuritiesDepository@gtht.com"
CHANNEL = "国泰海通"
# Subject格式: 860050583856李宝程20260526
_SUBJECT_DATE_RE = re.compile(r"(\d{8})$")


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _already_imported(db: Session, data_date: str) -> bool:
    """Check if data for this data_date is already imported."""
    from app.models.portfolio import PortfolioRecord
    return (
        db.query(PortfolioRecord)
        .filter(
            PortfolioRecord.channel == CHANNEL,
            PortfolioRecord.data_date == data_date,
        )
        .first() is not None
    )


def _fetch_xlsx_from_imap(
    output_dir: Path,
    email_account: str,
    password: str,
    imap_host: str,
) -> list[tuple[Path, str]]:
    """
    扫描最近 20 封来自国泰海通的邮件，返回所有附件。

    Returns: [(xlsx_path, data_date_str), ...] 按邮件新旧排序（最新在前）
    """
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        imaplib.Commands["ID"] = ("AUTH",)
        client._simple_command("ID", '("name" "Nanobot" "version" "1.0")')
        status, _ = client.select("INBOX")
        if status != "OK":
            raise RuntimeError("Cannot open INBOX")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        results: list[tuple[Path, str]] = []
        for msg_id in reversed(data[0].split()[-50:]):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(fetched[0][1])

            sender = _decode_mime_header(msg.get("From", ""))
            if SENDER_KEYWORD not in sender:
                continue

            subject = _decode_mime_header(msg.get("Subject", ""))
            m = _SUBJECT_DATE_RE.search(subject)
            if not m:
                continue
            data_date = m.group(1)  # e.g. "20260526"

            for part in msg.walk():
                filename = _decode_mime_header(part.get_filename() or "")
                if not filename.lower().endswith(".xlsx"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                xlsx_path = output_dir / f"gtht_{data_date}.xlsx"
                xlsx_path.write_bytes(payload)
                results.append((xlsx_path, data_date))
                break  # one attachment per email

            if len(results) >= 7:
                break

        # Sort oldest-first so the newest data_date wins when same week overwrites
        results.sort(key=lambda x: x[1])
        return results
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


def _parse_xlsx(xlsx_path: Path, data_date: str) -> tuple[list[dict], date]:
    """
    解析国泰海通资产证明 Excel，提取持仓明细。

    Returns: (items, statement_date)
    items 格式: [{"资产项": name, "金额(元)": value, "币种": "CNY", "基金代码": code}, ...]
    """
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(xlsx_path.read_bytes()))
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Parse statement date from data_date string (yyyyMMdd)
    statement_date = date(int(data_date[:4]), int(data_date[4:6]), int(data_date[6:8]))

    # Find header row: contains "证券代码" and "市值"
    header_idx = -1
    for i, row in enumerate(rows):
        row_strs = [str(v).strip() if v is not None else "" for v in row]
        if "证券代码" in row_strs and "市值" in row_strs:
            header_idx = i
            break

    if header_idx == -1:
        raise ValueError("Excel 解析失败：未找到持仓明细表头")

    header = [str(v).strip() if v is not None else "" for v in rows[header_idx]]
    col = {name: idx for idx, name in enumerate(header) if name}

    # Required columns
    for c in ("资产类别", "证券简称", "证券代码", "市值"):
        if c not in col:
            raise ValueError(f"Excel 缺少必要列：{c}")

    items: list[dict] = []
    for row in rows[header_idx + 1:]:
        if not row or all(v is None for v in row):
            break

        asset_type = str(row[col["资产类别"]] or "").strip()
        if asset_type not in ("证券", "资金"):
            continue

        name = str(row[col["证券简称"]] or "").strip()
        if not name:
            continue

        try:
            value = float(row[col["市值"]] or 0)
        except (TypeError, ValueError):
            continue

        if value <= 0:
            continue

        code = str(row[col.get("证券代码", -1)] or "").strip() if "证券代码" in col else ""

        items.append({
            "资产项": name,
            "金额(元)": value,
            "币种": "CNY",
            "基金代码": code,
        })

    if not items:
        raise ValueError("Excel 解析失败：未找到持仓数据")

    return items, statement_date


def pull_gtht_statement(db: Session) -> list[ImportResult]:
    """
    拉取国泰海通每日持仓邮件，逐只证券写入 PortfolioRecord。

    - 扫描最近邮件，导入所有尚未入库的 data_date
    - 非交易日无邮件时返回空列表
    """
    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    results: list[ImportResult] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        emails = _fetch_xlsx_from_imap(
            output_dir=tmp_path,
            email_account=imap_email,
            password=imap_password,
            imap_host=imap_host,
        )

        if not emails:
            logger.info("GTHT: no emails found")
            return results

        for xlsx_path, data_date in emails:
            if _already_imported(db, data_date):
                logger.info(f"GTHT: {data_date} already imported, skipping")
                continue

            items, statement_date = _parse_xlsx(xlsx_path, data_date)
            total = sum(i["金额(元)"] for i in items)
            logger.info(
                f"GTHT: date={data_date}, {len(items)} positions, "
                f"total={total:,.2f} CNY"
            )

            result = import_from_parsed_data(
                db=db,
                items=items,
                file_name=f"gtht_{data_date}.xlsx",
                record_date=statement_date,
                source="email_pull",
                channel=CHANNEL,
            )
            results.append(result)

    return results
