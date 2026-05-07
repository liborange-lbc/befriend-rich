"""
Alipay (蚂蚁基金) PDF parser.

Handles two PDF types from "李宝程的支付宝业务凭证" emails:
1. 资产证明 — current fund holdings
2. 交易明细 — transaction history (used to compute weekly investment)
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlipayHolding:
    """One fund holding from 资产证明 PDF."""
    fund_name: str
    fund_code: str
    shares: float
    nav: float          # 单位净值
    nav_date: date
    amount: float       # 资产小计


@dataclass(frozen=True)
class AlipayTransaction:
    """One transaction from 交易明细 PDF."""
    trade_date: date
    trade_type: str     # 定投买入, 用户买入, 转托管入, etc.
    fund_name: str
    fund_code: str
    confirmed_amount: float   # 确认金额
    confirmed_shares: float   # 确认份额
    fee: float
    confirm_date: date


def _clean_newlines(val: str | None) -> str:
    """Remove embedded newlines from pdfplumber cell values."""
    if not val:
        return ""
    return re.sub(r"\s+", " ", val.replace("\n", " ")).strip()


def _clean_fund_name(val: str | None) -> str:
    """Clean fund name: collapse whitespace and remove spurious spaces in Chinese text."""
    name = _clean_newlines(val)
    # Remove spaces between Chinese characters / between Chinese and ASCII fund suffixes
    # e.g. "大成纳斯达克100ETF联接 (QDII)A" -> "大成纳斯达克100ETF联接(QDII)A"
    # e.g. "创金合信中证红利低波动指 数A" -> "创金合信中证红利低波动指数A"
    name = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fffA-Za-z0-9(（])", "", name)
    name = re.sub(r"(?<=[A-Za-z0-9)）])\s+(?=[\u4e00-\u9fffA-Za-z])", "", name)
    return name


def _parse_date_compact(s: str) -> date | None:
    """Parse date from formats like '20260417' or '2026/04/17' or '2026年04月17日'."""
    s = _clean_newlines(s).replace(" ", "")
    # YYYYMMDD
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # YYYY/MM/DD (possibly with time)
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # YYYY年MM月DD日
    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _parse_float(s: str | None) -> float:
    """Parse float from string, handling None and '/'."""
    if not s:
        return 0.0
    s = _clean_newlines(s).replace(",", "")
    if s in ("/", "-", ""):
        return 0.0
    return float(s)


def parse_asset_proof(pdf_path: str | Path) -> tuple[list[AlipayHolding], date]:
    """
    Parse 资产证明 PDF.

    Returns:
        (holdings, statement_date)
    """
    import pdfplumber

    holdings: list[AlipayHolding] = []
    statement_date = date.today()

    with pdfplumber.open(str(pdf_path)) as pdf:
        # Extract statement date from first page text
        first_text = pdf.pages[0].extract_text() or ""
        dt = _parse_date_compact(first_text)
        if dt:
            statement_date = dt
        else:
            # Try "截止至YYYY-MM-DD" pattern
            m = re.search(r"截止至(\d{4}[-/]\d{1,2}[-/]\d{1,2})", first_text)
            if m:
                d = _parse_date_compact(m.group(1))
                if d:
                    statement_date = d

        # Extract table from all pages
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                # Check if this is the holdings table (header has 基金名称)
                header = [_clean_newlines(c) for c in (table[0] or [])]
                if "基金名称" not in " ".join(header):
                    continue

                for row in table[1:]:
                    if not row or len(row) < 8:
                        continue
                    name = _clean_fund_name(row[2])
                    code = _clean_newlines(row[3])
                    if not name or not code:
                        continue
                    nav_date = _parse_date_compact(row[6] or "")
                    holdings.append(AlipayHolding(
                        fund_name=name,
                        fund_code=code,
                        shares=_parse_float(row[4]),
                        nav=_parse_float(row[5]),
                        nav_date=nav_date or statement_date,
                        amount=_parse_float(row[7]),
                    ))

    logger.info(f"Parsed {len(holdings)} holdings from asset proof, date={statement_date}")
    return holdings, statement_date


def parse_transaction_detail(pdf_path: str | Path) -> list[AlipayTransaction]:
    """
    Parse 交��明细 PDF.

    Returns list of transactions.
    """
    import pdfplumber

    transactions: list[AlipayTransaction] = []
    pending_continuation: dict | None = None

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                for row in table:
                    if not row or len(row) < 12:
                        continue
                    # Skip header row
                    raw_first = _clean_newlines(row[0])
                    if "订单号" in raw_first:
                        continue

                    trade_type = _clean_newlines(row[2])
                    fund_code = _clean_newlines(row[5])

                    # Handle page-break continuation rows (empty trade_type and code)
                    if not trade_type and not fund_code:
                        # This is a continuation of the previous row that split across pages
                        if pending_continuation:
                            fund_name_extra = _clean_fund_name(row[3])
                            if fund_name_extra:
                                pending_continuation["fund_name"] = _clean_fund_name(
                                    pending_continuation["fund_name"] + fund_name_extra
                                )
                        continue

                    # Flush pending continuation
                    if pending_continuation:
                        transactions.append(AlipayTransaction(**pending_continuation))
                        pending_continuation = None

                    fund_name = _clean_fund_name(row[3])
                    trade_time = _clean_newlines(row[1])
                    trade_date = _parse_date_compact(trade_time)
                    confirm_date_str = _clean_newlines(row[11])
                    confirm_date = _parse_date_compact(confirm_date_str)

                    entry = {
                        "trade_date": trade_date or date.today(),
                        "trade_type": trade_type,
                        "fund_name": fund_name,
                        "fund_code": fund_code,
                        "confirmed_amount": _parse_float(row[8]),
                        "confirmed_shares": _parse_float(row[9]),
                        "fee": _parse_float(row[10]),
                        "confirm_date": confirm_date or (trade_date or date.today()),
                    }

                    # Check if this row might continue on next page
                    pending_continuation = entry

                # Flush at end of each page's table
                if pending_continuation:
                    transactions.append(AlipayTransaction(**pending_continuation))
                    pending_continuation = None

    logger.info(f"Parsed {len(transactions)} transactions from detail PDF")
    return transactions


def compute_weekly_investments(
    transactions: list[AlipayTransaction],
    reference_date: date,
) -> dict[str, float]:
    """
    Compute weekly investment per fund code.

    Uses ISO week of reference_date. Sums confirmed_amount for all
    transaction types (定投买入, 用户买入, 转托管入) in the same week.

    Args:
        transactions: Parsed transactions
        reference_date: The date of the asset proof (determines the week)

    Returns:
        {fund_code: total_weekly_investment}
    """
    ref_iso = reference_date.isocalendar()
    ref_week = (ref_iso[0], ref_iso[1])

    weekly: dict[str, float] = {}
    for txn in transactions:
        txn_iso = txn.trade_date.isocalendar()
        txn_week = (txn_iso[0], txn_iso[1])
        if txn_week != ref_week:
            continue
        weekly[txn.fund_code] = weekly.get(txn.fund_code, 0.0) + txn.confirmed_amount

    logger.info(
        f"Weekly investments for week {ref_week}: "
        f"{len(weekly)} funds, total={sum(weekly.values()):.2f}"
    )
    return weekly
