import email
import imaplib
import logging
import re
import tempfile
import zipfile
from datetime import date, datetime
from email.header import decode_header, make_header
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.services.config_service import get_config_with_db
from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

DEFAULT_SUBJECT = "微众银行电子版资产对账单"
STOP_TOKENS = ("交易明细", "持仓明细", "风险提示", "温馨提示", "免责声明")
SUMMARY_EXCLUDE_NAMES = {"微众卡", "稳健理财", "基金", "合计"}


# --- PDF parsing functions (copied from webank-statement-to-excel skill) ---


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    return safe or "attachment.zip"


def _fetch_latest_zip_from_imap(
    output_dir: Path,
    email_account: str,
    password: str,
    imap_host: str,
    subject: str = DEFAULT_SUBJECT,
    mailbox: str = "INBOX",
) -> Path:
    """Fetch the latest zip attachment matching the subject from IMAP."""
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        # 163 IMAP may require client ID before mailbox SELECT
        imaplib.Commands["ID"] = ("AUTH",)
        client_id = ("name", "Nanobot", "version", "1.0", "vendor", "Nanobot")
        client._simple_command("ID", '("' + '" "'.join(client_id) + '")')
        status, _ = client.select(mailbox)
        if status != "OK":
            raise RuntimeError(f"Cannot open mailbox: {mailbox}")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        message_ids = data[0].split()
        for msg_id in reversed(message_ids[-100:]):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            raw = fetched[0][1]
            msg = email.message_from_bytes(raw)
            msg_subject = _decode_mime_header(msg.get("Subject"))
            if subject not in msg_subject:
                continue

            for part in msg.walk():
                filename = part.get_filename()
                if not filename:
                    continue
                name = _decode_mime_header(filename)
                if not name.lower().endswith(".zip"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_name = f"mail_{ts}_{_sanitize_filename(name)}"
                out = output_dir / save_name
                out.write_bytes(payload)
                return out
        raise FileNotFoundError(f'No zip attachment found for subject "{subject}"')
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


def _unzip_pdf(zip_path: Path, output_dir: Path, password: str) -> Path:
    """Decrypt zip and extract PDF."""
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
        if not members:
            raise FileNotFoundError("No PDF file inside zip attachment")
        member = members[0]
        try:
            data = zf.read(member, pwd=password.encode("utf-8"))
        except RuntimeError as exc:
            raise RuntimeError("Failed to decrypt zip. Check zip password.") from exc
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = output_dir / f"mail_{ts}.pdf"
    pdf_path.write_bytes(data)
    return pdf_path


def _extract_text(pdf_path: Path) -> str:
    """Extract all text from PDF using pdfplumber."""
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def _asset_overview_lines(full_text: str) -> list[str]:
    """Extract lines from the asset overview section."""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    start_idx = next((i for i, ln in enumerate(lines) if "资产概览" in ln), -1)
    if start_idx == -1:
        return []
    segment: list[str] = []
    for ln in lines[start_idx + 1:]:
        if any(token in ln for token in STOP_TOKENS):
            break
        segment.append(ln)
    return segment


def _parse_amount(raw: str) -> float:
    cleaned = raw.replace("¥", "").replace("￥", "").replace(",", "").strip()
    return float(cleaned)


def _parse_assets(lines: Iterable[str]) -> list[dict]:
    """Parse asset lines into structured data."""
    rows: list[dict] = []
    seen: set[tuple[str, float]] = set()
    pattern = re.compile(
        r"^(?P<name>[\u4e00-\u9fffA-Za-z0-9（）()·\-/\s]{2,}?)\s+(?P<amount>[+-]?[¥￥]?\s?\d[\d,]*(?:\.\d{1,2})?)$"
    )
    for ln in lines:
        match = pattern.match(ln)
        if not match:
            continue
        name = re.sub(r"\s+", " ", match.group("name")).strip()
        if name in SUMMARY_EXCLUDE_NAMES:
            continue
        amount = _parse_amount(match.group("amount"))
        key = (name, amount)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"资产项": name, "金额(元)": amount, "币种": "CNY"})
    return rows


def _determine_statement_date(pdf_text: str) -> date:
    """Extract statement date from PDF text."""
    # Try to find date pattern like "2026年04月17日" or "2026-04-17"
    patterns = [
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})-(\d{1,2})-(\d{1,2})",
        r"(\d{4})/(\d{1,2})/(\d{1,2})",
    ]
    for pat in patterns:
        match = re.search(pat, pdf_text)
        if match:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                continue
    # Fallback to today
    return date.today()


def _get_imap_credentials(db: Session) -> tuple[str, str, str, str]:
    """Read IMAP credentials from SystemConfig."""
    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")
    zip_password = get_config_with_db(db, "webank_zip_password", "090391")
    return imap_email, imap_password, imap_host, zip_password


def pull_latest_statement(db: Session, force: bool = False) -> ImportResult:
    """
    Pull latest WeBank statement from 163 email and import.

    Flow:
    1. Read IMAP credentials from SystemConfig
    2. Connect to 163 email via IMAP
    3. Search for latest WeBank statement email
    4. Download zip attachment
    5. Decrypt zip -> extract PDF
    6. Parse PDF -> extract asset overview data
    7. Convert to standard format
    8. Call import_from_parsed_data() to complete import

    Raises:
        ValueError: IMAP credentials not configured
        FileNotFoundError: No matching email found
        RuntimeError: IMAP connection or zip decryption failed
    """
    imap_email, imap_password, imap_host, zip_password = _get_imap_credentials(db)

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Fetch zip from IMAP
        zip_path = _fetch_latest_zip_from_imap(
            output_dir=tmp_path,
            email_account=imap_email,
            password=imap_password,
            imap_host=imap_host,
        )
        logger.info(f"Downloaded zip: {zip_path}")

        # Decrypt and extract PDF
        pdf_path = _unzip_pdf(zip_path, tmp_path, zip_password)
        logger.info(f"Extracted PDF: {pdf_path}")

        # Parse PDF
        pdf_text = _extract_text(pdf_path)
        lines = _asset_overview_lines(pdf_text)
        items = _parse_assets(lines)

        if not items:
            raise ValueError("PDF 解析失败：未找到资产概览数据")

        # Determine statement date
        statement_date = _determine_statement_date(pdf_text)
        logger.info(f"Statement date: {statement_date}, items: {len(items)}")

        # Import
        result = import_from_parsed_data(
            db=db,
            items=items,
            file_name=f"email_{statement_date.isoformat()}.pdf",
            record_date=statement_date,
            source="email_pull",
            force=force,
        )

        return result
