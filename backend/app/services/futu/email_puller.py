"""
Futu email puller — fetch 富途证券保证金综合账户证券日结单 from IMAP.

每天 no_reply@stmt.futuhk.com 发送加密 PDF 附件，
解析「期末概览」中股票和基金的市值，导入 PortfolioRecord，channel='富途证券'。
"""

import email
import imaplib
import io
import logging
import re
from datetime import date
from email.header import decode_header, make_header

from sqlalchemy.orm import Session

from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

FUTU_SENDER = "stmt.futuhk.com"
FUTU_SUBJECT = "證券日結單"
CHANNEL = "富途证券"
_PDF_PASSWORD = "11630391"


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _fetch_attachment_bytes(
    imap_host: str,
    email_account: str,
    password: str,
) -> tuple[bytes, str] | None:
    """拉取最新一封富途日结单邮件的 PDF 附件。"""
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        imaplib.Commands["ID"] = ("AUTH",)
        client._simple_command("ID", '("name" "Nanobot" "version" "1.0" "vendor" "Nanobot")')
        client.select("INBOX")

        _, data = client.search(None, "ALL")
        message_ids = data[0].split() if data[0] else []

        for msg_id in reversed(message_ids):
            _, fetched = client.fetch(msg_id, "(RFC822)")
            if not fetched or not fetched[0]:
                continue
            msg = email.message_from_bytes(fetched[0][1])
            sender = _decode_mime_header(msg.get("From", ""))
            subject = _decode_mime_header(msg.get("Subject", ""))
            if FUTU_SENDER not in sender or FUTU_SUBJECT not in subject:
                continue

            logger.info(f"Futu statement email: {msg.get('Date', '')} | {subject}")
            for part in msg.walk():
                fn = _decode_mime_header(part.get_filename() or "")
                if not fn or not fn.lower().endswith(".pdf"):
                    continue
                payload = part.get_payload(decode=True)
                if payload:
                    logger.info(f"Attachment: {fn} ({len(payload)} bytes)")
                    return payload, fn

        logger.info("No Futu daily statement email with PDF attachment found")
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


def _extract_text(pdf_bytes: bytes) -> str:
    """提取 PDF 文本（需要密码）。"""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes), password=_PDF_PASSWORD) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _parse_statement_date(text: str) -> date:
    """从 PDF 文本提取日结单日期。"""
    # 格式如 "2026/05/20" 或主题行里的日期
    m = re.search(r"(\d{4})/(\d{2})/(\d{2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return date.today()


def _parse_holdings(text: str) -> list[dict]:
    """
    解析「期末概览」中股票和基金持仓的市值。

    股票行格式：
      02618(京東物流) SEHK HKD 400 13.6900 - 5,476.00 2,464.20 1,916.60 0.3500
      → code=02618, name=京東物流, currency=HKD, market_value=5,476.00 (token[6])

    基金行格式：
      HK0000502390(華夏精選貨幣基金) HKD 172.327656 11.1182 2026/05/20 0.00 1,915.97
      → code=HK0000502390, name=華夏精選貨幣基金, currency=HKD, market_value=1,915.97 (token[-1])
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 找「期末概览」区段（繁体：期末概覽）
    end_start = next(
        (i for i, ln in enumerate(lines) if "期末概覽" in ln or "期末概览" in ln), -1
    )
    if end_start == -1:
        logger.warning("Futu PDF: 期末概覽 section not found, scanning full text")
        end_start = 0

    # 结束于「重要提示」或文末
    section_end = next(
        (i for i in range(end_start + 1, len(lines)) if "重要提示" in lines[i]),
        len(lines),
    )

    # 匹配 CODE(NAME) 格式，如 02618(京東物流) 或 HK0000502390(華夏精選貨幣基金)
    code_name_re = re.compile(r"^([A-Z0-9.]{2,15})\((.+?)\)$")
    amount_re = re.compile(r"^[\d,]+\.\d+$")

    currency_map = {"HKD": "HKD", "USD": "USD", "CNH": "CNY", "CNY": "CNY"}

    items: list[dict] = []
    seen: set[str] = set()

    for ln in lines[end_start:section_end]:
        tokens = ln.split()
        if not tokens:
            continue

        m = code_name_re.match(tokens[0])
        if not m:
            continue

        code = m.group(1)
        name = m.group(2).strip()

        # 股票行：tokens[2] = 货币，tokens[6] = 市值（固定位置）
        # 基金行：tokens[1] = 货币，tokens[-1] = 市值
        # 区分：股票行有 SEHK/NYSE/NASDAQ 等交易所字段
        if len(tokens) >= 7 and tokens[1] in ("SEHK", "NYSE", "NASDAQ", "AMEX", "SGX"):
            # 股票
            currency = currency_map.get(tokens[2], "HKD")
            raw_amount = tokens[6].replace(",", "") if len(tokens) > 6 else ""
        else:
            # 基金
            currency = currency_map.get(tokens[1], "HKD") if len(tokens) > 1 else "HKD"
            raw_amount = tokens[-1].replace(",", "") if tokens[-1] != tokens[0] else ""

        try:
            amount = float(raw_amount)
        except (ValueError, IndexError):
            continue

        if amount <= 0:
            continue

        key = f"{code}_{currency}"
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "资产项": name,
            "金额(元)": amount,
            "币种": currency,
            "基金代码": code,
        })

    return items


def pull_futu_email_statement(db: Session) -> ImportResult:
    """
    从邮箱拉取富途日结单并导入持仓数据。

    IMAP 凭据来自 SystemConfig (imap_email / imap_password / imap_host)。
    """
    from app.services.config_service import get_config_with_db

    imap_email = get_config_with_db(db, "imap_email", "")
    imap_password = get_config_with_db(db, "imap_password", "")
    imap_host = get_config_with_db(db, "imap_host", "imap.163.com")

    if not imap_email or not imap_password:
        raise ValueError("请先在设置页配置邮箱凭据")

    result = _fetch_attachment_bytes(imap_host, imap_email, imap_password)
    if result is None:
        raise FileNotFoundError("未找到富途日结单邮件附件")

    pdf_bytes, filename = result
    text = _extract_text(pdf_bytes)

    if not text.strip():
        raise ValueError("PDF 文本提取失败")

    statement_date = _parse_statement_date(text)
    items = _parse_holdings(text)

    if not items:
        raise ValueError(
            f"持仓解析失败：未提取到任何持仓。PDF 前500字：\n{text[:500]}"
        )

    logger.info(
        f"Futu email: date={statement_date}, holdings={len(items)}, "
        f"total={sum(i['金额(元)'] for i in items):.2f}"
    )

    return import_from_parsed_data(
        db=db,
        items=items,
        file_name=f"futu_email_{statement_date.isoformat()}.pdf",
        record_date=statement_date,
        source="futu_email",
        channel=CHANNEL,
    )
