import logging
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.classification import ClassModel, FundClassMap
from app.models.fund import Fund
from app.models.import_log import ImportLog
from app.models.portfolio import PortfolioRecord
from app.response import ok
from app.schemas.import_data import ImportLogResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    record_date: date = Query(..., description="持仓日期，如 2026-04-17"),
    force: bool = Query(default=False, description="是否强制覆盖已导入数据"),
    db: Session = Depends(get_db),
) -> dict:
    """Upload Excel file and execute full import pipeline."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 .xlsx 文件")

    content = await file.read()

    from app.services.webank.importer import DuplicateImportError, import_from_excel

    try:
        result = import_from_excel(
            db=db,
            file_content=content,
            file_name=file.filename,
            record_date=record_date,
            force=force,
        )
    except DuplicateImportError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ok({
        "total_items": result.total_items,
        "matched_funds": result.matched_funds,
        "new_funds_created": result.new_funds_created,
        "records_imported": result.records_imported,
        "classification_results": result.classification_results,
        "snapshot_generated": result.snapshot_generated,
        "import_log_id": result.import_log_id,
    })


@router.post("/pull-email")
async def pull_email(
    force: bool = Query(default=False, description="是否强制覆盖已导入的数据"),
    db: Session = Depends(get_db),
) -> dict:
    """Pull latest statement from 163 email and import."""
    from app.services.webank.email_puller import pull_latest_statement
    from app.services.webank.importer import DuplicateImportError

    try:
        result = pull_latest_statement(db, force=force)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateImportError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ok({
        "email_found": True,
        "statement_date": None,  # Will be set from import log
        "total_items": result.total_items,
        "matched_funds": result.matched_funds,
        "new_funds_created": result.new_funds_created,
        "records_imported": result.records_imported,
        "classification_results": result.classification_results,
        "import_log_id": result.import_log_id,
    })


def _build_record_response(record: PortfolioRecord, fund: Fund, db: Session) -> dict:
    """Build a single record response with fund info."""
    return {
        "id": record.id,
        "fund_id": fund.id,
        "fund_code": fund.code,
        "fund_name": fund.name,
        "record_date": record.record_date.isoformat(),
        "amount": round(record.amount, 2),
        "amount_cny": round(record.amount_cny, 2),
        "profit": round(record.profit or 0.0, 2),
        "currency": fund.currency,
    }


def _get_group_value(
    record_resp: dict,
    group_key: str,
    record_date: date,
    db: Session,
) -> str:
    """Get the group value for a record based on the group key."""
    if group_key == "date":
        return record_date.isoformat()
    elif group_key == "date_week":
        iso = record_date.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    elif group_key == "date_month":
        return record_date.strftime("%Y-%m")
    elif group_key == "currency":
        return record_resp["currency"]
    elif group_key.startswith("model_"):
        model_id_str = group_key.replace("model_", "")
        try:
            model_id = int(model_id_str)
        except ValueError:
            return "未知"
        from app.models.classification import ClassCategory
        mapping = (
            db.query(FundClassMap)
            .filter(FundClassMap.fund_id == record_resp["fund_id"], FundClassMap.model_id == model_id)
            .first()
        )
        if not mapping:
            return "未分类"
        cat = db.query(ClassCategory).filter(ClassCategory.id == mapping.category_id).first()
        return cat.name if cat else "未分类"
    return "未知"


@router.get("/records")
def list_import_records(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    fund_id: int | None = Query(default=None),
    keyword: str = Query(default=""),
    model_id: int | None = Query(default=None),
    category_id: int | None = Query(default=None),
    group_by: str | None = Query(default=None, description="逗号分隔的分组维度: date,model_<id>,currency"),
    db: Session = Depends(get_db),
) -> dict:
    """Query asset records with filtering and grouping support."""
    query = db.query(PortfolioRecord)

    if start_date:
        query = query.filter(PortfolioRecord.record_date >= start_date)
    if end_date:
        query = query.filter(PortfolioRecord.record_date <= end_date)
    if fund_id:
        query = query.filter(PortfolioRecord.fund_id == fund_id)

    # Keyword filter: join with Fund
    if keyword:
        fund_ids = (
            db.query(Fund.id)
            .filter((Fund.name.contains(keyword)) | (Fund.code.contains(keyword)))
            .all()
        )
        fund_id_list = [fid for (fid,) in fund_ids]
        query = query.filter(PortfolioRecord.fund_id.in_(fund_id_list))

    # Classification filter
    if model_id is not None and category_id is not None:
        mapping_fund_ids = (
            db.query(FundClassMap.fund_id)
            .filter(FundClassMap.model_id == model_id, FundClassMap.category_id == category_id)
            .all()
        )
        mapped_ids = [fid for (fid,) in mapping_fund_ids]
        query = query.filter(PortfolioRecord.fund_id.in_(mapped_ids))
    elif model_id is not None:
        mapping_fund_ids = (
            db.query(FundClassMap.fund_id)
            .filter(FundClassMap.model_id == model_id)
            .all()
        )
        mapped_ids = [fid for (fid,) in mapping_fund_ids]
        query = query.filter(PortfolioRecord.fund_id.in_(mapped_ids))

    records = query.order_by(PortfolioRecord.record_date.desc()).all()

    # Build record responses
    record_responses: list[dict] = []
    for r in records:
        fund = db.query(Fund).filter(Fund.id == r.fund_id).first()
        if not fund:
            continue
        record_responses.append(_build_record_response(r, fund, db))

    # Grouped mode
    if group_by:
        group_keys = [k.strip() for k in group_by.split(",") if k.strip()]
        groups: dict[tuple, list[dict]] = defaultdict(list)

        for resp in record_responses:
            record_date_val = date.fromisoformat(resp["record_date"])
            key_parts: list[str] = []
            for gk in group_keys:
                key_parts.append(_get_group_value(resp, gk, record_date_val, db))
            groups[tuple(key_parts)].append(resp)

        grouped_results: list[dict] = []
        for key_tuple, recs in groups.items():
            key_dict = dict(zip(group_keys, key_tuple))
            grouped_results.append({
                "key": key_dict,
                "total_amount": round(sum(r["amount"] for r in recs), 2),
                "total_amount_cny": round(sum(r["amount_cny"] for r in recs), 2),
                "total_profit": round(sum(r["profit"] for r in recs), 2),
                "count": len(recs),
                "records": recs,
            })

        # Sort by key
        grouped_results.sort(key=lambda g: tuple(g["key"].values()))

        summary = {
            "total_amount_cny": round(sum(r["amount_cny"] for r in record_responses), 2),
            "total_profit": round(sum(r["profit"] for r in record_responses), 2),
            "record_count": len(record_responses),
        }

        return ok({"groups": grouped_results, "summary": summary})

    # Detail mode
    total_amount_cny = sum(r["amount_cny"] for r in record_responses)
    total_profit = sum(r["profit"] for r in record_responses)

    return ok(
        record_responses,
        meta={
            "total": len(record_responses),
            "summary": {
                "total_amount_cny": round(total_amount_cny, 2),
                "total_profit": round(total_profit, 2),
            },
        },
    )


@router.put("/records/{record_id}")
def update_import_record(
    record_id: int,
    amount: float = Query(...),
    profit: float = Query(default=0.0),
    fund_code: str | None = Query(default=None),
    fund_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Update a portfolio record's amount/profit and optionally its fund's code/name."""
    record = db.query(PortfolioRecord).filter(PortfolioRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    fund = db.query(Fund).filter(Fund.id == record.fund_id).first()

    # Update fund code/name if provided
    if fund and (fund_code is not None or fund_name is not None):
        if fund_code is not None and fund_code != fund.code:
            dup = db.query(Fund).filter(Fund.code == fund_code, Fund.id != fund.id).first()
            if dup:
                raise HTTPException(status_code=400, detail=f"基金代码 {fund_code} 已被其他基金使用")
            fund.code = fund_code
        if fund_name is not None:
            fund.name = fund_name

    amount_cny = amount
    if fund and fund.currency == "USD":
        from app.services.market_data.exchange_rate import get_latest_rate
        rate = get_latest_rate(db, "USD/CNY")
        amount_cny = amount * rate
    record.amount = amount
    record.amount_cny = amount_cny
    record.profit = profit
    db.commit()
    db.refresh(record)
    from app.services.portfolio.snapshot import generate_snapshot
    generate_snapshot(db, record.record_date)
    return ok({"updated": True, "id": record_id})


@router.delete("/records/{record_id}")
def delete_import_record(
    record_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Delete a single portfolio record."""
    record = db.query(PortfolioRecord).filter(PortfolioRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    record_date = record.record_date
    db.delete(record)
    db.commit()
    from app.services.portfolio.snapshot import generate_snapshot
    generate_snapshot(db, record_date)
    return ok({"deleted": True, "id": record_id})


@router.post("/records/batch-delete")
def batch_delete_import_records(
    ids: list[int] = Query(..., description="要删除的记录ID列表"),
    db: Session = Depends(get_db),
) -> dict:
    """Batch delete portfolio records."""
    records = db.query(PortfolioRecord).filter(PortfolioRecord.id.in_(ids)).all()
    if not records:
        raise HTTPException(status_code=404, detail="未找到要删除的记录")
    dates = {r.record_date for r in records}
    deleted_count = len(records)
    for r in records:
        db.delete(r)
    db.commit()
    from app.services.portfolio.snapshot import generate_snapshot
    for d in dates:
        generate_snapshot(db, d)
    return ok({"deleted": deleted_count})


@router.get("/logs")
def list_import_logs(
    limit: int = Query(default=20),
    db: Session = Depends(get_db),
) -> dict:
    """Query import history logs."""
    logs = (
        db.query(ImportLog)
        .order_by(ImportLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return ok([ImportLogResponse.model_validate(log).model_dump() for log in logs])


@router.get("/group-dimensions")
def get_group_dimensions(db: Session = Depends(get_db)) -> dict:
    """Get available group dimensions."""
    dimensions: list[dict] = [
        {"key": "date", "label": "日期（精确）", "type": "date"},
        {"key": "date_week", "label": "日期（周）", "type": "date"},
        {"key": "date_month", "label": "日期（月）", "type": "date"},
        {"key": "currency", "label": "币种", "type": "enum"},
    ]

    # Add classification model dimensions
    models = db.query(ClassModel).all()
    for model in models:
        dimensions.append({
            "key": f"model_{model.id}",
            "label": model.name,
            "type": "classification",
        })

    return ok(dimensions)
