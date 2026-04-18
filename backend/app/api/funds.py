from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.response import ok
from app.schemas.fund import FundCreate, FundResponse, FundUpdate
from app.services.backfill_task import get_task_status, start_backfill

router = APIRouter()


@router.post("")
def create_fund(body: FundCreate, db: Session = Depends(get_db)):
    existing = db.query(Fund).filter(Fund.code == body.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="基金代码已存在")
    fund = Fund(**body.model_dump())
    db.add(fund)
    db.commit()
    db.refresh(fund)
    start_backfill(fund.id)
    return ok(FundResponse.model_validate(fund).model_dump())


@router.get("")
def list_funds(
    keyword: str = Query(default="", description="搜索关键词"),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Fund)
    if keyword:
        query = query.filter(
            (Fund.name.contains(keyword)) | (Fund.code.contains(keyword))
        )
    if is_active is not None:
        query = query.filter(Fund.is_active == is_active)
    total = query.count()
    funds = query.offset((page - 1) * page_size).limit(page_size).all()
    return ok(
        [FundResponse.model_validate(f).model_dump() for f in funds],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.get("/{fund_id}")
def get_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    return ok(FundResponse.model_validate(fund).model_dump())


@router.put("/{fund_id}")
def update_fund(fund_id: int, body: FundUpdate, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(fund, key, value)
    db.commit()
    db.refresh(fund)
    return ok(FundResponse.model_validate(fund).model_dump())


@router.get("/{fund_id}/backfill-status")
def fund_backfill_status(fund_id: int):
    status = get_task_status(fund_id)
    return ok(status)


@router.delete("/{fund_id}")
def delete_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    db.delete(fund)
    db.commit()
    return ok({"deleted": True})
