"""
东方财富证券「投资者股份持有证明」邮件解析器

每周从 jy_manager@18.cn 发送的加密 PDF 中提取持仓明细：
每只证券一条 PortfolioRecord（渠道=东方财富），每日无数据由
job_weekly_data_completion 递延上周数据。
"""

import email
import imaplib
import logging
import re
import tempfile
from datetime import date, timedelta
from email.header import decode_header, make_header
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.config_service import get_config_with_db
from app.services.webank.importer import ImportResult, import_from_parsed_data, normalize_to_monday

logger = logging.getLogger(__name__)

SUBJECT_KEYWORD = "投资者股份持有证明"
SENDER_KEYWORD = "jy_manager@18.cn"
CHANNEL = "东方财富"
PDF_PASSWORD = "090391"

# 截至 2026年05月25日
_DATE_RE = re.compile(r"截至\s*(\d{4})年(\d{1,2})月(\d{1,2})日")
# 证券名称行：名称 6位代码 市场描述 数量 市值
_HOLDING_RE = re.compile(
    r"^(\S+)\s+(\d{6})\s+\S+\s+[\d,]+\s+([\d,.]+)\s*$", re.MULTILINE
)


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _this_week_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def _already_imported(db: Session, monday: date) -> bool:
    from app.models.portfolio import PortfolioRecord

    return (
        db.query(PortfolioRecord)
        .filter(
            PortfolioRecord.channel == CHANNEL,
            PortfolioRecord.record_date == monday,
        )
        .first()
        is not None
    )


def _fetch_pdf_from_imap(
    output_dir: Path,
    email_account: str,
    password: str,
    imap_host: str,
    after_date: date | None = None,
) -> tuple[Path, date] | None:
    """
    扫描最近 200 封邮件，找到「投资者股份持有证明」PDF 附件。
    返回 (pdf_path, email_date) 或 None。
    """
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        imaplib.Commands["ID"] = ("AUTH",)
        client_id = ("name", "Nanobot", "version", "1.0", "vendor", "Nanobot")
        client._simple_command("ID", '("' + '" "'.join(client_id) + '")')
        status, _ = client.select("INBOX")
        if status != "OK":
            raise RuntimeError("Cannot open INBOX")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        for msg_id in reversed(data[0].split()[-200:]):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(fetched[0][1])

            subject = _decode_mime_header(msg.get("Subject", ""))
            sender = _decode_mime_header(msg.get("From", ""))
            if SUBJECT_KEYWORD not in subject:
                continue
            if SENDER_KEYWORD not in sender:
                continue

            from email.utils import parsedate_to_datetime
            try:
                email_date = parsedate_to_datetime(msg.get("Date", "")).date()
            except Exception:
                email_date = date.today()

            if after_date and email_date < after_date:
                break

            for part in msg.walk():
                filename = _decode_mime_header(part.get_filename() or "")
                if not filename.lower().endswith(".pdf"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                pdf_path = output_dir / f"eastmoney_{email_date.isoformat()}.pdf"
                pdf_path.write_bytes(payload)
                logger.info(f"Downloaded PDF: {pdf_path} (email date: {email_date})")
                return pdf_path, email_date
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()

    return None


def _decrypt_pdf(encrypted_path: Path, output_dir: Path) -> Path:
    """Decrypt password-protected PDF using pikepdf."""
    import pikepdf

    decrypted_path = output_dir / f"decrypted_{encrypted_path.name}"
    with pikepdf.open(str(encrypted_path), password=PDF_PASSWORD) as pdf:
        pdf.save(str(decrypted_path))
    return decrypted_path


def _parse_holdings(pdf_path: Path) -> tuple[list[dict], date]:
    """
    从 PDF 提取持仓明细和截止日期。

    Returns:
        (items, statement_date)
        items: [{"资产项": name, "金额(元)": value, "币种": "CNY", "基金代码": code}, ...]
    """
    import pdfplumber

    text_chunks: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text_chunks.append(page.extract_text() or "")
    text = "\n".join(text_chunks)

    # Extract statement date
    m = _DATE_RE.search(text)
    if m:
        statement_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    else:
        statement_date = date.today()

    # Extract security holdings (skip the "市值总计" summary line)
    items: list[dict] = []
    for m in _HOLDING_RE.finditer(text):
        name = m.group(1)
        code = m.group(2)
        value_str = m.group(3).replace(",", "")
        try:
            value = float(value_str)
        except ValueError:
            continue
        if value <= 0:
            continue
        items.append({
            "资产项": name,
            "金额(元)": value,
            "币种": "CNY",
            "基金代码": code,
        })

    if not items:
        raise ValueError("PDF 解析失败：未找到证券持仓数据")

    return items, statement_date


def pull_eastmoney_statement(db: Session) -> ImportResult | None:
    """
    拉取本周东方财富股份持有证明，逐只证券写入 PortfolioRecord。

    无本周邮件时返回 None，递延由 job_weekly_data_completion 处理。
    """
    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    this_monday = _this_week_monday()

    if _already_imported(db, this_monday):
        logger.info(f"Eastmoney: already imported for week {this_monday}, skipping")
        return None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        result = _fetch_pdf_from_imap(
            output_dir=tmp_path,
            email_account=imap_email,
            password=imap_password,
            imap_host=imap_host,
            after_date=this_monday,
        )

        if result is None:
            logger.info(f"Eastmoney: no email found this week ({this_monday}), skipping")
            return None

        pdf_path, email_date = result
        decrypted_path = _decrypt_pdf(pdf_path, tmp_path)
        items, statement_date = _parse_holdings(decrypted_path)

        total = sum(i["金额(元)"] for i in items)
        logger.info(
            f"Eastmoney: statement_date={statement_date}, "
            f"{len(items)} holdings, total={total:.2f}"
        )

        return import_from_parsed_data(
            db=db,
            items=items,
            file_name=f"eastmoney_{statement_date.isoformat()}.pdf",
            record_date=statement_date,
            source="email_pull",
            channel=CHANNEL,
        )
