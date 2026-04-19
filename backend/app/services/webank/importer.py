import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models.fund import Fund
from app.models.import_log import ImportLog
from app.models.portfolio import PortfolioRecord
from app.services.market_data.exchange_rate import get_latest_rate
from app.services.portfolio.snapshot import generate_snapshot
from app.services.webank.classifier import classify_funds_with_ai
from app.services.webank.fund_matcher import find_or_create_fund

logger = logging.getLogger(__name__)


class DuplicateImportError(Exception):
    """Raised when a duplicate import is detected and force is not set."""

    pass


@dataclass(frozen=True)
class ImportResult:
    total_items: int
    matched_funds: int
    new_funds_created: int
    records_imported: int
    classification_results: dict = field(default_factory=dict)
    snapshot_generated: bool = False
    import_log_id: int = 0


def _parse_excel(file_content: bytes) -> list[dict]:
    """
    Parse WeBank Excel file and extract asset items.

    Returns:
        List of {"资产项": str, "金额(元)": float, "币种": str}
    """
    from openpyxl import load_workbook
    from io import BytesIO

    wb = load_workbook(BytesIO(file_content), read_only=True)

    # Try to find "资产概览" sheet, fallback to first sheet
    if "资产概览" in wb.sheetnames:
        ws = wb["资产概览"]
    else:
        ws = wb.active

    rows_data = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows_data:
        raise ValueError("Excel 文件为空")

    # Find header row
    header = None
    header_idx = -1
    for i, row in enumerate(rows_data):
        row_strs = [str(cell).strip() if cell else "" for cell in row]
        if "资产项" in row_strs and any("金额" in s for s in row_strs):
            header = row_strs
            header_idx = i
            break

    if header is None:
        raise ValueError("缺少必要列：资产项, 金额(元)")

    # Find column indices
    name_col = next(i for i, h in enumerate(header) if h == "资产项")
    amount_col = next(
        (i for i, h in enumerate(header) if "金额" in h),
        None,
    )
    if amount_col is None:
        raise ValueError("缺少必要列：金额(元)")

    currency_col = next(
        (i for i, h in enumerate(header) if "币种" in h),
        None,
    )

    items: list[dict] = []
    for row in rows_data[header_idx + 1:]:
        if not row or all(cell is None for cell in row):
            continue

        name = str(row[name_col]).strip() if row[name_col] else ""
        if not name:
            continue

        try:
            raw_amount = row[amount_col]
            if isinstance(raw_amount, str):
                raw_amount = raw_amount.replace(",", "").replace("¥", "").replace("￥", "").strip()
            amount = float(raw_amount)
        except (ValueError, TypeError):
            logger.warning(f"Skipping row with invalid amount: {name}")
            continue

        if amount < 0:
            logger.warning(f"Skipping row with negative amount: {name} = {amount}")
            continue

        currency = "CNY"
        if currency_col is not None and row[currency_col]:
            currency = str(row[currency_col]).strip()

        items.append({
            "资产项": name,
            "金额(元)": amount,
            "币种": currency,
        })

    return items


def import_from_parsed_data(
    db: Session,
    items: list[dict],
    file_name: str,
    record_date: date,
    source: str = "excel_upload",
    force: bool = False,
) -> ImportResult:
    """
    Import parsed asset data into the system.

    Args:
        db: Database session
        items: List of {"资产项": str, "金额(元)": float, "币种": str}
        file_name: Original file name for logging
        record_date: Portfolio record date
        source: Import source type
        force: Whether to force overwrite existing data

    Returns:
        ImportResult with import statistics
    """
    # Check for duplicate import
    existing_log = (
        db.query(ImportLog)
        .filter(ImportLog.import_date == record_date, ImportLog.status == "success")
        .first()
    )
    if existing_log and not force:
        raise DuplicateImportError(
            f"日期 {record_date} 已有导入记录 (id={existing_log.id})，请使用 force=true 覆盖"
        )

    if existing_log and force:
        # Delete existing records for this date to allow re-import
        db.query(PortfolioRecord).filter(
            PortfolioRecord.record_date == record_date,
        ).delete()
        db.commit()

    total_items = len(items)
    matched_funds = 0
    new_funds_created = 0
    new_fund_ids: list[int] = []
    fund_records: list[tuple[Fund, float, str]] = []

    # Match or create funds
    for item in items:
        fund_name = item["资产项"]
        amount = item["金额(元)"]
        currency = item["币种"]

        fund, is_new = find_or_create_fund(db, fund_name, currency)

        if is_new:
            new_funds_created += 1
            new_fund_ids.append(fund.id)
        else:
            matched_funds += 1

        fund_records.append((fund, amount, currency))

    # AI classification for new funds
    classification_results: dict = {"classified": 0, "models_covered": 0}
    if new_fund_ids:
        try:
            cls_map = classify_funds_with_ai(db, new_fund_ids)
            classification_results["classified"] = len(cls_map)
            if cls_map:
                all_models: set[int] = set()
                for fund_cls in cls_map.values():
                    all_models.update(fund_cls.keys())
                classification_results["models_covered"] = len(all_models)
        except Exception as e:
            logger.error(f"AI classification failed: {e}")

    # Get exchange rate for currency conversion
    usd_rate = get_latest_rate(db, "USD/CNY")

    # Write portfolio records (upsert)
    # Track pending records by fund_id to handle in-batch duplicates
    pending_records: dict[int, dict] = {}
    for fund, amount, currency in fund_records:
        # Calculate amount_cny
        if currency == "USD":
            amount_cny = amount * usd_rate
        else:
            amount_cny = amount

        # Calculate profit: current amount - previous period amount
        previous_record = (
            db.query(PortfolioRecord)
            .filter(
                PortfolioRecord.fund_id == fund.id,
                PortfolioRecord.record_date < record_date,
            )
            .order_by(PortfolioRecord.record_date.desc())
            .first()
        )
        profit = (amount - previous_record.amount) if previous_record else 0.0

        # Use dict to deduplicate by fund_id (last write wins)
        pending_records[fund.id] = {
            "amount": amount,
            "amount_cny": amount_cny,
            "profit": profit,
        }

    records_imported = 0
    for fund_id, data in pending_records.items():
        existing_record = (
            db.query(PortfolioRecord)
            .filter(
                PortfolioRecord.fund_id == fund_id,
                PortfolioRecord.record_date == record_date,
            )
            .first()
        )
        if existing_record:
            existing_record.amount = data["amount"]
            existing_record.amount_cny = data["amount_cny"]
            existing_record.profit = data["profit"]
        else:
            db.add(PortfolioRecord(
                fund_id=fund_id,
                record_date=record_date,
                amount=data["amount"],
                amount_cny=data["amount_cny"],
                profit=data["profit"],
            ))
        records_imported += 1

    db.commit()

    # Generate snapshot
    snapshot_generated = False
    try:
        result = generate_snapshot(db, record_date)
        snapshot_generated = result is not None
    except Exception as e:
        logger.error(f"Snapshot generation failed: {e}")

    # Create import log
    import_log = ImportLog(
        import_date=record_date,
        source=source,
        file_name=file_name,
        record_count=records_imported,
        new_funds_count=new_funds_created,
        status="success",
    )
    db.add(import_log)
    db.commit()
    db.refresh(import_log)

    return ImportResult(
        total_items=total_items,
        matched_funds=matched_funds,
        new_funds_created=new_funds_created,
        records_imported=records_imported,
        classification_results=classification_results,
        snapshot_generated=snapshot_generated,
        import_log_id=import_log.id,
    )


def import_from_excel(
    db: Session,
    file_content: bytes,
    file_name: str,
    record_date: date,
    force: bool = False,
) -> ImportResult:
    """
    Full pipeline: parse Excel -> match/create funds -> AI classify -> write records -> snapshot.

    Args:
        db: Database session
        file_content: Excel file binary content
        file_name: Original file name
        record_date: Portfolio record date
        force: Whether to force overwrite existing data

    Returns:
        ImportResult with import statistics

    Raises:
        ValueError: File format error
        DuplicateImportError: Date already imported (and force=False)
    """
    items = _parse_excel(file_content)
    if not items:
        raise ValueError("Excel 文件中未找到有效的资产数据")

    return import_from_parsed_data(
        db=db,
        items=items,
        file_name=file_name,
        record_date=record_date,
        source="excel_upload",
        force=force,
    )
