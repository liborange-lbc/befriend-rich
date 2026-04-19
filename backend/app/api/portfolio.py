import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.response import ok
from app.schemas.portfolio import (
    PortfolioRecordBatchCreate,
    PortfolioRecordCreate,
    PortfolioRecordResponse,
    PortfolioRecordUpdate,
    PortfolioSnapshotResponse,
)
from app.services.market_data.exchange_rate import get_latest_rate
from app.services.portfolio.snapshot import generate_snapshot

router = APIRouter()


@router.post("/records")
def create_record(body: PortfolioRecordCreate, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.id == body.fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")

    existing = (
        db.query(PortfolioRecord)
        .filter(
            PortfolioRecord.fund_id == body.fund_id,
            PortfolioRecord.record_date == body.record_date,
        )
        .first()
    )

    amount_cny = body.amount
    if fund.currency == "USD":
        rate = get_latest_rate(db)
        amount_cny = body.amount * rate

    if existing:
        existing.amount = body.amount
        existing.amount_cny = amount_cny
        existing.profit = body.profit
        db.commit()
        db.refresh(existing)
        record = existing
    else:
        record = PortfolioRecord(
            fund_id=body.fund_id,
            record_date=body.record_date,
            amount=body.amount,
            amount_cny=amount_cny,
            profit=body.profit or 0.0,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    return ok(PortfolioRecordResponse.model_validate(record).model_dump())


@router.post("/records/batch")
def batch_create_records(body: PortfolioRecordBatchCreate, db: Session = Depends(get_db)):
    results = []
    for item in body.records:
        fund = db.query(Fund).filter(Fund.id == item.fund_id).first()
        if not fund:
            continue
        amount_cny = item.amount
        if fund.currency == "USD":
            rate = get_latest_rate(db)
            amount_cny = item.amount * rate

        existing = (
            db.query(PortfolioRecord)
            .filter(
                PortfolioRecord.fund_id == item.fund_id,
                PortfolioRecord.record_date == item.record_date,
            )
            .first()
        )
        if existing:
            existing.amount = item.amount
            existing.amount_cny = amount_cny
            existing.profit = item.profit
        else:
            record = PortfolioRecord(
                fund_id=item.fund_id,
                record_date=item.record_date,
                amount=item.amount,
                amount_cny=amount_cny,
                profit=item.profit or 0.0,
            )
            db.add(record)
    db.commit()

    if body.records:
        snapshot_date = body.records[0].record_date
        generate_snapshot(db, snapshot_date)

    return ok({"message": f"已录入 {len(body.records)} 条记录"})


@router.get("/records")
def list_records(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    fund_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(PortfolioRecord)
    if start_date:
        query = query.filter(PortfolioRecord.record_date >= start_date)
    if end_date:
        query = query.filter(PortfolioRecord.record_date <= end_date)
    if fund_id:
        query = query.filter(PortfolioRecord.fund_id == fund_id)
    records = query.order_by(PortfolioRecord.record_date.desc()).all()
    return ok([PortfolioRecordResponse.model_validate(r).model_dump() for r in records])


@router.get("/records/dates")
def get_record_dates(db: Session = Depends(get_db)):
    """Return all distinct dates that have portfolio records."""
    from sqlalchemy import func
    dates = (
        db.query(PortfolioRecord.record_date)
        .distinct()
        .order_by(PortfolioRecord.record_date)
        .all()
    )
    return ok([d[0].isoformat() for d in dates])


@router.get("/records/latest")
def get_latest_records(
    target_date: date | None = Query(default=None, description="指定日期，默认最新"),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    if target_date:
        selected_date = target_date
    else:
        selected_date = db.query(func.max(PortfolioRecord.record_date)).scalar()
    if not selected_date:
        return ok([])
    records = (
        db.query(PortfolioRecord)
        .filter(PortfolioRecord.record_date == selected_date)
        .all()
    )
    return ok(
        [PortfolioRecordResponse.model_validate(r).model_dump() for r in records],
        meta={"latest_date": selected_date.isoformat()},
    )


@router.put("/records/{record_id}")
def update_record(record_id: int, body: PortfolioRecordUpdate, db: Session = Depends(get_db)):
    record = db.query(PortfolioRecord).filter(PortfolioRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    generate_snapshot(db, record.record_date)
    return ok(PortfolioRecordResponse.model_validate(record).model_dump())


@router.get("/breakdown")
def get_breakdown(
    target_date: date | None = Query(default=None, description="指定日期，默认最新"),
    db: Session = Depends(get_db),
):
    """Real-time compute model breakdown from portfolio records + fund class maps."""
    from sqlalchemy import func
    from app.models.classification import ClassCategory, ClassModel, FundClassMap

    if target_date:
        selected_date = target_date
    else:
        selected_date = db.query(func.max(PortfolioRecord.record_date)).scalar()
    if not selected_date:
        return ok({})

    records = (
        db.query(PortfolioRecord)
        .filter(PortfolioRecord.record_date == selected_date)
        .all()
    )
    if not records:
        return ok({})

    fund_amounts = {r.fund_id: r.amount_cny for r in records}
    mappings = db.query(FundClassMap).filter(FundClassMap.fund_id.in_(fund_amounts.keys())).all()
    models = {m.id: m.name for m in db.query(ClassModel).all()}

    breakdown: dict[str, dict[str, float]] = {}
    for mapping in mappings:
        model_name = models.get(mapping.model_id)
        if not model_name:
            continue
        category = db.query(ClassCategory).filter(ClassCategory.id == mapping.category_id).first()
        if not category:
            continue
        amount = fund_amounts.get(mapping.fund_id, 0)
        if amount <= 0:
            continue
        if model_name not in breakdown:
            breakdown[model_name] = {}
        cat_name = category.name
        breakdown[model_name][cat_name] = breakdown[model_name].get(cat_name, 0) + amount

    return ok(breakdown)


@router.get("/trend")
def get_trend(
    end_date: date | None = Query(default=None),
    start_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get total_amount_cny per record date for trend chart (real-time, no snapshots)."""
    from sqlalchemy import func

    query = db.query(
        PortfolioRecord.record_date,
        func.sum(PortfolioRecord.amount_cny).label("total"),
    ).group_by(PortfolioRecord.record_date)

    if start_date:
        query = query.filter(PortfolioRecord.record_date >= start_date)
    if end_date:
        query = query.filter(PortfolioRecord.record_date <= end_date)

    rows = query.order_by(PortfolioRecord.record_date).all()
    return ok([{"date": r[0].isoformat(), "total": round(r[1], 2)} for r in rows])


@router.get("/snapshots")
def list_snapshots(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(PortfolioSnapshot)
    if start_date:
        query = query.filter(PortfolioSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.filter(PortfolioSnapshot.snapshot_date <= end_date)
    snapshots = query.order_by(PortfolioSnapshot.snapshot_date).all()
    return ok([PortfolioSnapshotResponse.model_validate(s).model_dump() for s in snapshots])


@router.get("/top5")
def get_top5(
    target_date: date | None = Query(default=None, description="指定日期，默认最新"),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    if target_date:
        selected_date = target_date
    else:
        selected_date = db.query(func.max(PortfolioRecord.record_date)).scalar()
    if not selected_date:
        return ok([])
    all_records = (
        db.query(PortfolioRecord)
        .filter(PortfolioRecord.record_date == selected_date)
        .order_by(PortfolioRecord.amount_cny.desc())
        .all()
    )
    total = sum(r.amount_cny for r in all_records)
    result = []
    for i, r in enumerate(all_records[:5], 1):
        fund = db.query(Fund).filter(Fund.id == r.fund_id).first()
        result.append({
            "rank": i,
            "fund_id": r.fund_id,
            "fund_name": fund.name if fund else "Unknown",
            "fund_code": fund.code if fund else "",
            "amount_cny": round(r.amount_cny, 2),
            "percentage": round(r.amount_cny / total * 100, 2) if total > 0 else 0,
            "profit": r.profit,
        })
    return ok(result)


@router.post("/snapshots/generate")
def trigger_snapshot(snapshot_date: date = Query(...), db: Session = Depends(get_db)):
    result = generate_snapshot(db, snapshot_date)
    return ok(result)
