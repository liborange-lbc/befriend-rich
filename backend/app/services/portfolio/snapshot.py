import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.classification import ClassCategory, FundClassMap
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.services.market_data.exchange_rate import get_latest_rate

logger = logging.getLogger(__name__)


def generate_snapshot(db: Session, snapshot_date: date):
    records = (
        db.query(PortfolioRecord)
        .filter(PortfolioRecord.record_date == snapshot_date)
        .all()
    )
    if not records:
        return None

    usd_rate = get_latest_rate(db, "USD/CNY")
    total_cny = 0.0

    for record in records:
        fund = db.query(Fund).filter(Fund.id == record.fund_id).first()
        if fund and fund.currency == "USD":
            record.amount_cny = record.amount * usd_rate
        else:
            record.amount_cny = record.amount
        total_cny += record.amount_cny

    model_breakdown = _build_model_breakdown(db, records)

    existing = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.snapshot_date == snapshot_date)
        .first()
    )
    if existing:
        existing.total_amount_cny = total_cny
        existing.model_breakdown = json.dumps(model_breakdown, ensure_ascii=False)
    else:
        snapshot = PortfolioSnapshot(
            snapshot_date=snapshot_date,
            total_amount_cny=total_cny,
            model_breakdown=json.dumps(model_breakdown, ensure_ascii=False),
        )
        db.add(snapshot)

    db.commit()
    return {"total_amount_cny": total_cny, "model_breakdown": model_breakdown}


def _build_model_breakdown(db: Session, records: list[PortfolioRecord]) -> dict:
    """Build model breakdown storing amounts at actual mapped category level with hierarchy info.

    Structure: {model_name: {category_name: amount, ...}, model_name__tree: {parent: [children], ...}}
    """
    from app.models.classification import ClassModel

    fund_amounts = {r.fund_id: r.amount_cny for r in records}
    mappings = db.query(FundClassMap).filter(FundClassMap.fund_id.in_(fund_amounts.keys())).all()

    breakdown: dict = {}
    for mapping in mappings:
        category = db.query(ClassCategory).filter(ClassCategory.id == mapping.category_id).first()
        if not category:
            continue
        model = db.query(ClassModel).filter(ClassModel.id == mapping.model_id).first()
        if not model:
            continue

        model_name = model.name
        cat_name = category.name

        if model_name not in breakdown:
            breakdown[model_name] = {}
        if cat_name not in breakdown[model_name]:
            breakdown[model_name][cat_name] = 0.0
        breakdown[model_name][cat_name] += fund_amounts.get(mapping.fund_id, 0)

    return breakdown
