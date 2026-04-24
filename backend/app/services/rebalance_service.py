import logging
from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.classification import ClassCategory, ClassModel, FundClassMap
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord
from app.models.rebalance import RebalanceTarget

logger = logging.getLogger(__name__)


def get_targets(db: Session) -> list[dict]:
    """Get all rebalance targets for the first classification model."""
    model = db.query(ClassModel).first()
    if not model:
        return []

    categories = db.query(ClassCategory).filter(ClassCategory.model_id == model.id).all()
    targets = {t.category_id: t.target_pct for t in db.query(RebalanceTarget).filter(RebalanceTarget.model_id == model.id).all()}

    return [
        {
            "category_id": c.id,
            "category_name": c.name,
            "target_pct": targets.get(c.id, 0.0),
        }
        for c in categories
    ]


def set_targets(db: Session, targets: list[dict]) -> int:
    """Set rebalance targets. Each item: {category_id: int, target_pct: float}."""
    model = db.query(ClassModel).first()
    if not model:
        return 0

    count = 0
    for t in targets:
        cat_id = t["category_id"]
        pct = t["target_pct"]
        existing = (
            db.query(RebalanceTarget)
            .filter(RebalanceTarget.model_id == model.id, RebalanceTarget.category_id == cat_id)
            .first()
        )
        if existing:
            existing.target_pct = pct
        else:
            db.add(RebalanceTarget(model_id=model.id, category_id=cat_id, target_pct=pct))
        count += 1
    db.commit()
    return count


def get_rebalance_analysis(db: Session) -> dict:
    """Compute drift analysis and rebalancing recommendations."""
    model = db.query(ClassModel).first()
    if not model:
        return {"total_value": 0, "categories": []}

    # Get latest portfolio records
    latest_date_row = db.query(PortfolioRecord.record_date).order_by(desc(PortfolioRecord.record_date)).first()
    if not latest_date_row:
        return {"total_value": 0, "categories": []}

    latest_date = latest_date_row[0]
    records = db.query(PortfolioRecord).filter(PortfolioRecord.record_date == latest_date).all()
    total_value = sum(r.amount_cny or r.amount for r in records)

    if total_value <= 0:
        return {"total_value": 0, "categories": []}

    # Map funds to categories
    mappings = db.query(FundClassMap).filter(FundClassMap.model_id == model.id).all()
    fund_to_cat: dict[int, int] = {}
    for m in mappings:
        fund_to_cat[m.fund_id] = m.category_id

    # Sum amounts per category
    cat_amounts: dict[int, float] = {}
    for r in records:
        cat_id = fund_to_cat.get(r.fund_id, -1)
        cat_amounts[cat_id] = cat_amounts.get(cat_id, 0) + (r.amount_cny or r.amount)

    # Get targets
    categories = {c.id: c.name for c in db.query(ClassCategory).filter(ClassCategory.model_id == model.id).all()}
    targets = {t.category_id: t.target_pct for t in db.query(RebalanceTarget).filter(RebalanceTarget.model_id == model.id).all()}

    results = []
    for cat_id in set(list(categories.keys()) + list(cat_amounts.keys())):
        if cat_id == -1:
            cat_name = "未分类"
        else:
            cat_name = categories.get(cat_id, f"ID:{cat_id}")

        actual_amount = cat_amounts.get(cat_id, 0)
        actual_pct = actual_amount / total_value * 100
        target_pct = targets.get(cat_id, 0.0)
        drift = actual_pct - target_pct
        target_amount = total_value * target_pct / 100
        action_amount = target_amount - actual_amount

        results.append({
            "category_id": cat_id,
            "category_name": cat_name,
            "actual_amount": round(actual_amount, 2),
            "actual_pct": round(actual_pct, 2),
            "target_pct": target_pct,
            "drift": round(drift, 2),
            "target_amount": round(target_amount, 2),
            "action_amount": round(action_amount, 2),
            "action": "买入" if action_amount > 0 else ("卖出" if action_amount < 0 else "持有"),
        })

    results.sort(key=lambda x: abs(x["drift"]), reverse=True)

    return {
        "total_value": round(total_value, 2),
        "record_date": latest_date.isoformat(),
        "categories": results,
    }
