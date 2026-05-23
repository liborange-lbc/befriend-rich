"""
Longbridge email puller — fetch 长桥证券账户日结单 from IMAP.

每天 noreply@longbridge.hk 发送「账户日结单」，附件为 PDF（偶尔为 ZIP→PDF）。
解析「投资组合详情」中各持仓的市值，导入 PortfolioRecord，channel='长桥证券'。

附件密码（如有）写死在此处，ECS 上无需访问本地密钥文件。
"""

import email
import imaplib
import io
import logging
import re
import zipfile
from datetime import date
from email.header import decode_header, make_header

from sqlalchemy.orm import Session

from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

LONGBRIDGE_SENDER = "longbridge.hk"       # From 头包含此字符串
LONGBRIDGE_SUBJECT = "账户日结单"
CHANNEL = "长桥证券"
# 附件密码（目前日结单 PDF 不加密，此密码备用于 ZIP 附件场景）
_PDF_PASSWORD = "11630391"

# 跳过期权行（持仓市值可能为负，不纳入资产统计）
_SKIP_SECTIONS = {"期权"}


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def _fetch_attachment_bytes(
    imap_host: str,
    email_account: str,
    password: str,
) -> tuple[bytes, str] | None:
    """
    从 IMAP 拉取最新一封长桥日结单邮件的附件。

    163 IMAP FROM 搜索对中文发件人不稳定，改为扫全部邮件在 Python 侧过滤。

    Returns:
        (attachment_bytes, filename) 或 None
    """
    client = imaplib.IMAP4_SSL(imap_host)
    try:
        client.login(email_account, password)
        imaplib.Commands["ID"] = ("AUTH",)
        client._simple_command("ID", '("name" "Nanobot" "version" "1.0" "vendor" "Nanobot")')
        status, _ = client.select("INBOX")
        if status != "OK":
            raise RuntimeError("Cannot open mailbox")

        status, data = client.search(None, "ALL")
        if status != "OK":
            raise RuntimeError("IMAP search failed")

        message_ids = data[0].split()
        # 从最新往旧扫，找第一封匹配的日结单
        for msg_id in reversed(message_ids):
            status, fetched = client.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(fetched[0][1])
            sender = _decode_mime_header(msg.get("From", ""))
            subject = _decode_mime_header(msg.get("Subject", ""))
            if LONGBRIDGE_SENDER not in sender or LONGBRIDGE_SUBJECT not in subject:
                continue

            logger.info(f"Longbridge statement email: {msg.get('Date', '')} | {subject}")
            for part in msg.walk():
                fn = _decode_mime_header(part.get_filename() or "")
                if not fn:
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                if fn.lower().rsplit(".", 1)[-1] in ("pdf", "zip"):
                    logger.info(f"Attachment: {fn} ({len(payload)} bytes)")
                    return payload, fn

        logger.info("No Longbridge daily statement email with attachment found")
        return None
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


def _extract_pdf_bytes(attachment: bytes, filename: str) -> bytes:
    """从附件提取 PDF（支持直接 PDF 或 ZIP→PDF）。"""
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(attachment)) as zf:
            pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
            if not pdf_names:
                raise FileNotFoundError("ZIP 内无 PDF 文件")
            return zf.read(pdf_names[0], pwd=_PDF_PASSWORD.encode("utf-8"))
    return attachment


def _extract_text(pdf_bytes: bytes) -> str:
    """提取 PDF 文本，尝试带密码和不带密码两种方式。"""
    import pdfplumber

    # 先尝试不加密码（大多数日结单无密码）
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            if text.strip():
                return text
    except Exception:
        pass

    # fallback：带密码
    with pdfplumber.open(io.BytesIO(pdf_bytes), password=_PDF_PASSWORD) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _parse_statement_date(text: str) -> date:
    """从 PDF 文本提取对账日期（取第一个匹配）。"""
    patterns = [
        r"(\d{4})\.(\d{2})\.(\d{2})",   # 2026.05.22
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                continue
    return date.today()


def _parse_holdings(text: str) -> list[dict]:
    """
    解析「投资组合详情」各持仓的市值。

    列结构（固定 9 个尾部数字字段）：
      CODE  NAME  期初持仓  变更  期末持仓  价格  持仓市值  成本  浮亏  保证金%  保证金

    策略（token-based）：
    1. 定位「投资组合详情」~「基金交易详情」区段
    2. 合并跨行的基金名称（连续行首非代码格式的行追加到上一行）
    3. 按小节标题记录当前货币，跳过「期权」小节
    4. 每行 tokenize，识别尾部连续数字字段，market_value = 尾部第 5 个
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # 定位区段
    start = next((i for i, ln in enumerate(lines) if "投资组合详情" in ln), 0)
    end_keywords = {"基金交易详情", "其他资金出入明细", "其他持仓出入明细", "责任说明", "交易记录"}
    end = next(
        (i for i in range(start + 1, len(lines)) if any(kw in lines[i] for kw in end_keywords)),
        len(lines),
    )

    # 合并因 PDF 换行被拆散的基金名称行
    # 判断：行首是 "股票代码格式"（大写字母/数字/HK开头等）则视为新行，否则追加到上一行
    code_start_re = re.compile(r"^[A-Z0-9]{1,12}(\.|[A-Z0-9])")
    merged: list[str] = []
    for ln in lines[start:end]:
        if merged and not code_start_re.match(ln) and not re.search(r"[;；]", ln):
            merged[-1] = merged[-1] + " " + ln
        else:
            merged.append(ln)

    section_re = re.compile(
        r"(股票|期权|余额通|基金)[^(]*\(.*?[;；]\s*(美元|港元|人民币|USD|HKD|CNY)\s*\)"
    )
    currency_map = {"美元": "USD", "港元": "HKD", "人民币": "CNY",
                    "USD": "USD", "HKD": "HKD", "CNY": "CNY"}

    num_re = re.compile(r"^-?[\d,]+\.?\d*%?$")

    def is_num(tok: str) -> bool:
        return bool(num_re.match(tok))

    # 第一遍：收集所有候选持仓行（行号、code、name、amount）
    # 第二遍：用「汇总 (XXX)」行反向确认每组的货币
    # 这样可以处理跨页时小节标题缺失的问题

    summary_re = re.compile(r"^汇总\s*[（(](美元|港元|人民币)[)）]")

    # 结构：(line_idx, code, name, amount)
    candidates: list[tuple[int, str, str, float]] = []
    skip_section = False
    current_currency = "USD"

    segment_lines = lines[start:end]

    for idx, ln in enumerate(segment_lines):
        m_sec = section_re.search(ln)
        if m_sec:
            skip_section = m_sec.group(1) in _SKIP_SECTIONS
            current_currency = currency_map.get(m_sec.group(2), "USD")
            continue

        if skip_section:
            continue
        if re.match(r"^(汇总|合计|小计|项⽬|项目)", ln):
            continue

        tokens = ln.split()
        if len(tokens) < 5:
            continue

        code = tokens[0]
        if not re.match(r"^[A-Z0-9.]{1,12}$", code):
            continue

        tail: list[str] = []
        for tok in reversed(tokens):
            if is_num(tok):
                tail.insert(0, tok)
            else:
                break

        if len(tail) < 9:
            continue

        market_value_raw = tail[-5].replace(",", "")
        try:
            amount = float(market_value_raw)
        except ValueError:
            continue

        if amount <= 0:
            continue

        name = " ".join(tokens[1: len(tokens) - len(tail)]).strip() or code
        candidates.append((idx, code, name, amount))

    # 第二遍：对每个候选项，向后找最近的「汇总 (XXX)」行确认货币
    def find_currency_after(from_idx: int) -> str:
        for ln in segment_lines[from_idx:from_idx + 10]:
            m = summary_re.match(ln.strip())
            if m:
                return currency_map.get(m.group(1), "USD")
        return current_currency  # fallback

    items: list[dict] = []
    seen: set[str] = set()

    for idx, code, name, amount in candidates:
        ccy = find_currency_after(idx + 1)
        key = f"{code}_{ccy}"
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "资产项": name,
            "金额(元)": amount,
            "币种": ccy,
            "基金代码": code,
        })

    return items


def pull_longbridge_email_statement(db: Session) -> ImportResult:
    """
    从邮箱拉取长桥日结单并导入持仓数据。

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
        raise FileNotFoundError("未找到长桥日结单邮件附件")

    attachment_bytes, filename = result
    pdf_bytes = _extract_pdf_bytes(attachment_bytes, filename)
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
        f"Longbridge email: date={statement_date}, holdings={len(items)}, "
        f"total={sum(i['金额(元)'] for i in items):.2f}"
    )

    return import_from_parsed_data(
        db=db,
        items=items,
        file_name=f"longbridge_email_{statement_date.isoformat()}.pdf",
        record_date=statement_date,
        source="longbridge_email",
        channel=CHANNEL,
    )
