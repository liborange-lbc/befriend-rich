import logging
import re
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.services.backfill_task import start_backfill

logger = logging.getLogger(__name__)

# Module-level cache for AkShare fund list
_fund_cache: dict[str, dict] | None = None
_fund_cache_time: float = 0
_CACHE_TTL = 86400  # 24 hours


def _normalize_name(name: str) -> str:
    """Normalize fund name for matching: remove spaces, unify brackets."""
    name = re.sub(r"\s+", "", name)
    name = name.replace("（", "(").replace("）", ")")
    return name


def _strip_share_suffix(name: str) -> str:
    """Remove share class suffix like A/B/C/D/E/F/Y from fund name."""
    return re.sub(r"[A-Fa-fYy]$", "", name)


def _strip_qualifiers(name: str) -> str:
    """Remove parenthetical qualifiers like (QDII), (LOF), (QDII-FOF), and currency suffixes."""
    name = re.sub(r"\((?:QDII[^)]*|LOF)\)", "", name)
    # Also strip trailing currency indicators
    name = re.sub(r"[-]?人民币$", "", name)
    name = re.sub(r"[-]?美元现汇$", "", name)
    name = re.sub(r"[-]?美元$", "", name)
    return name


def _get_share_suffix(name: str) -> str:
    """Extract share class suffix (A/B/C/D/E/F/Y) from end of name."""
    m = re.search(r"([A-Fa-fYy])$", name)
    return m.group(1).upper() if m else ""


def match_fund_by_name(db: Session, fund_name: str) -> Fund | None:
    """
    Match fund by name in database.
    Strategy:
    1. Exact match on Fund.name
    2. Normalized exact match (unified brackets, no spaces)
    NOTE: Do NOT strip share suffix (A/B/C) - they are different funds.
    """
    # 1. Exact match
    fund = db.query(Fund).filter(Fund.name == fund_name).first()
    if fund:
        return fund

    # 2. Normalized exact match
    normalized = _normalize_name(fund_name)
    all_funds = db.query(Fund).all()
    for f in all_funds:
        if _normalize_name(f.name) == normalized:
            return f

    return None


def _get_fund_cache() -> dict[str, dict]:
    """Get or refresh the AkShare fund name cache."""
    global _fund_cache, _fund_cache_time

    now = time.time()
    if _fund_cache is not None and (now - _fund_cache_time) < _CACHE_TTL:
        return _fund_cache

    try:
        import akshare as ak

        df = ak.fund_name_em()
        cache: dict[str, dict] = {}
        for _, row in df.iterrows():
            name = str(row.get("基金简称", ""))
            code = str(row.get("基金代码", ""))
            fund_type = str(row.get("基金类型", ""))
            if name and code:
                normalized = _normalize_name(name)
                cache[normalized] = {
                    "code": code,
                    "name": name,
                    "type": fund_type,
                }
        _fund_cache = cache
        _fund_cache_time = now
        logger.info(f"AkShare fund cache refreshed: {len(cache)} funds")
        return cache
    except Exception as e:
        logger.error(f"Failed to fetch AkShare fund list: {e}")
        if _fund_cache is not None:
            return _fund_cache
        return {}


def lookup_fund_code_via_akshare(fund_name: str) -> dict | None:
    """
    Look up fund code via AkShare's fund_name_em() interface.
    WeBank names often omit qualifiers like (QDII), (LOF), so we need fuzzy matching.

    Returns:
        {"code": "005918", "name": "...", "type": "..."} or None
    """
    cache = _get_fund_cache()
    if not cache:
        return None

    normalized = _normalize_name(fund_name)
    suffix = _get_share_suffix(normalized)

    # 1. Exact match
    if normalized in cache:
        return cache[normalized]

    # 2. Strip qualifiers from both sides and match
    # WeBank: "招商中证白酒指数C" vs AkShare: "招商中证白酒指数(LOF)C"
    norm_stripped_q = _strip_qualifiers(normalized)
    norm_stripped_qs = _strip_share_suffix(norm_stripped_q)

    # Build a reverse index: stripped_name -> [(key, val, suffix)]
    candidates: list[tuple[str, dict, str]] = []
    for key, val in cache.items():
        key_stripped_q = _strip_qualifiers(key)
        key_stripped_qs = _strip_share_suffix(key_stripped_q)
        if key_stripped_qs == norm_stripped_qs:
            candidates.append((key, val, _get_share_suffix(key)))

    if candidates:
        # Prefer same share class suffix
        for key, val, s in candidates:
            if s == suffix:
                return val
        # Otherwise return first candidate
        return candidates[0][1]

    # 3. Try with "-人民币" variations
    # WeBank: "嘉实美国成长股票(QDII)-人民币" vs AkShare: "嘉实美国成长股票人民币"
    variants = [
        norm_stripped_q.replace("-人民币", "人民币"),
        norm_stripped_q.replace("人民币", ""),
        norm_stripped_q.replace("-人民币", ""),
    ]
    for variant in variants:
        v_stripped = _strip_share_suffix(variant)
        for key, val in cache.items():
            key_stripped = _strip_share_suffix(_strip_qualifiers(key))
            if key_stripped == v_stripped:
                if _get_share_suffix(key) == suffix:
                    return val

    # Second pass without suffix requirement
    for variant in variants:
        v_stripped = _strip_share_suffix(variant)
        for key, val in cache.items():
            key_stripped = _strip_share_suffix(_strip_qualifiers(key))
            if key_stripped == v_stripped:
                return val

    # 4. Fuzzy containment: strip qualifiers from both then check containment
    if len(norm_stripped_qs) >= 6:
        best_match = None
        best_score = 0
        for key, val in cache.items():
            key_stripped = _strip_share_suffix(_strip_qualifiers(key))
            if len(key_stripped) < 4:
                continue
            # Check if one contains the other
            if norm_stripped_qs in key_stripped or key_stripped in norm_stripped_qs:
                overlap = min(len(norm_stripped_qs), len(key_stripped))
                # Penalize if suffix doesn't match
                score = overlap * 10 + (5 if _get_share_suffix(key) == suffix else 0)
                if score > best_score:
                    best_score = score
                    best_match = val
        if best_match and best_score >= 60:  # Require substantial overlap
            return best_match

    return None


def find_or_create_fund(
    db: Session,
    fund_name: str,
    currency: str = "CNY",
) -> tuple[Fund, bool]:
    """
    Find or create a fund. Returns (fund, is_new).
    1. Match by name in DB
    2. Look up code via AkShare
    3. Create Fund with akshare data_source if code found
    4. Create Fund with generated code and is_active=False if not found
    """
    # 1. Try DB match
    existing = match_fund_by_name(db, fund_name)
    if existing:
        return existing, False

    # 2. Try AkShare lookup (with retry)
    ak_result = None
    for attempt in range(2):
        ak_result = lookup_fund_code_via_akshare(fund_name)
        if ak_result:
            break
        if attempt == 0:
            logger.warning(f"AkShare lookup retry for: {fund_name}")

    if ak_result:
        # Check if code already exists in DB
        existing_by_code = db.query(Fund).filter(Fund.code == ak_result["code"]).first()
        if existing_by_code:
            return existing_by_code, False

        fund = Fund(
            code=ak_result["code"],
            name=fund_name,
            currency=currency,
            data_source="akshare",
            is_active=True,
        )
        db.add(fund)
        db.commit()
        db.refresh(fund)
        start_backfill(fund.id)
        logger.info(f"Created fund via AkShare: {fund_name} -> {ak_result['code']}")
        return fund, True

    # 4. Create with generated code, inactive
    ts = datetime.now().strftime("%H%M%S")
    generated_code = f"X{abs(hash(fund_name)) % 100000:05d}"
    # Ensure uniqueness
    while db.query(Fund).filter(Fund.code == generated_code).first():
        generated_code = f"X{abs(hash(fund_name + ts)) % 100000:05d}"

    fund = Fund(
        code=generated_code,
        name=fund_name,
        currency=currency,
        data_source="akshare",
        is_active=False,
    )
    db.add(fund)
    db.commit()
    db.refresh(fund)
    logger.warning(f"Created fund with generated code: {fund_name} -> {generated_code} (inactive)")
    return fund, True
