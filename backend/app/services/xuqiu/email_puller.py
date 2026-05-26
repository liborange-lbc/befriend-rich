"""
雪球基金资产证明邮件解析器

每周解析一封来自 kefu@danjuanfunds.com 的「雪球基金资产证明」PDF，
提取总持仓金额，以单条记录（渠道=雪球，基金=有知有行）写入 PortfolioRecord。

本周无邮件时不报错，由 job_weekly_data_completion 将上周数据递延到本周。
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

SUBJECT_KEYWORD = "雪球基金资产证明"
CHANNEL = "雪球"
FUND_NAME = "有知有行"
SENDER_KEYWORD = "danjuanfunds.com"

# Regex to capture the total net value/market value from the certificate body
_TOTAL_AMOUNT_RE = re.compile(
    r"基金资产余额净值/市值为人民币\s*([\d,]+\.?\d*)\s*元"
)
# Fallback: capture the bracketed amount in the English paragraph
_TOTAL_AMOUNT_BRACKET_RE = re.compile(
    r"is\s*\[\s*([\d,]+\.?\d*)\s*\]\s*CNY"
)
# Date in PDF: 截止到2026年05月25日
_DATE_RE = re.compile(r"截止到(\d{4})年(\d{1,2})月(\d{1,2})日")


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _this_week_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def _already_imported(db: Session, monday: date) -> bool:
    from app.models.portfolio import PortfolioRecord
    from app.services.webank.fund_matcher import find_or_create_fund

    fund, _ = find_or_create_fund(db, FUND_NAME, "CNY")
    exists = (
        db.query(PortfolioRecord)
        .filter(
            PortfolioRecord.fund_id == fund.id,
            PortfolioRecord.channel == CHANNEL,
            PortfolioRecord.record_date == monday,
        )
        .first()
    )
    return exists is not None


def _fetch_pdf_from_imap(
    output_dir: Path,
    email_account: str,
    password: str,
    imap_host: str,
    after_date: date | None = None,
) -> tuple[Path, date] | None:
    """
    Scan recent 100 emails for 雪球基金资产证明, download the PDF attachment.

    Returns (pdf_path, email_date) for the most recent matching email,
    or None if not found.  If after_date is given, only consider emails
    sent on or after that date.
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

        message_ids = data[0].split()
        for msg_id in reversed(message_ids[-200:]):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw = fetched[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_mime_header(msg.get("Subject", ""))
            sender = _decode_mime_header(msg.get("From", ""))
            if SUBJECT_KEYWORD not in subject:
                continue
            if SENDER_KEYWORD not in sender:
                continue

            # Parse email date
            from email.utils import parsedate_to_datetime
            try:
                email_dt = parsedate_to_datetime(msg.get("Date", ""))
                email_date = email_dt.date()
            except Exception:
                email_date = date.today()

            if after_date and email_date < after_date:
                break  # Emails are in ascending order; stop scanning older ones

            # Find PDF attachment
            for part in msg.walk():
                filename = _decode_mime_header(part.get_filename() or "")
                if not filename.lower().endswith(".pdf"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                pdf_path = output_dir / f"xuqiu_{email_date.isoformat()}.pdf"
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


def _extract_total_amount(pdf_path: Path) -> tuple[float, date]:
    """
    Extract total amount and statement date from the PDF.

    Returns (total_amount, statement_date).
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

    # Extract total amount
    m = _TOTAL_AMOUNT_RE.search(text)
    if not m:
        m = _TOTAL_AMOUNT_BRACKET_RE.search(text)
    if not m:
        raise ValueError("PDF 中未找到总持仓金额，请检查 PDF 格式")

    amount_str = m.group(1).replace(",", "")
    total_amount = float(amount_str)
    return total_amount, statement_date


def pull_xuqiu_statement(db: Session) -> ImportResult | None:
    """
    拉取本周雪球基金资产证明邮件，解析总持仓，写入 PortfolioRecord。

    Returns ImportResult on success, None if no email found this week
    (carry-forward is handled by job_weekly_data_completion).
    """
    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    this_monday = _this_week_monday()

    if _already_imported(db, this_monday):
        logger.info(f"Xuqiu: already imported for week {this_monday}, skipping")
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
            logger.info(f"Xuqiu: no email found this week ({this_monday}), skipping")
            return None

        pdf_path, email_date = result
        total_amount, statement_date = _extract_total_amount(pdf_path)

        logger.info(
            f"Xuqiu: statement_date={statement_date}, "
            f"email_date={email_date}, total={total_amount:.2f}"
        )

        return import_from_parsed_data(
            db=db,
            items=[{"资产项": FUND_NAME, "金额(元)": total_amount, "币种": "CNY"}],
            file_name=f"xuqiu_{statement_date.isoformat()}.pdf",
            record_date=statement_date,
            source="email_pull",
            channel=CHANNEL,
        )
