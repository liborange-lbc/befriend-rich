import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.response import ok
from app.schemas.fund import FundCreate, FundResponse, FundUpdate
from app.services.backfill_task import get_task_status, start_backfill

logger = logging.getLogger(__name__)

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


@router.post("/batch-fetch-fees")
def batch_fetch_fees(db: Session = Depends(get_db)):
    """批量获取所有活跃基金的持有费率"""
    funds = db.query(Fund).filter(Fund.is_active == True, Fund.management_fee == None).all()  # noqa: E711, E712
    results = {"success": 0, "failed": 0, "skipped": 0}
    try:
        import akshare as ak
    except ImportError:
        raise HTTPException(status_code=500, detail="akshare 未安装")

    for fund in funds:
        try:
            pure_code = fund.code.split(".")[0]
            df = ak.fund_individual_detail_info_xq(symbol=pure_code)
            other_fees = df[df["费用类型"] == "其他费用"]

            fee_map: dict[str, str] = {}
            for _, row in other_fees.iterrows():
                fee_map[row["条件或名称"]] = row["费用"]

            if "基金管理费" in fee_map:
                fund.management_fee = float(fee_map["基金管理费"])
            if "基金托管费" in fee_map:
                fund.custody_fee = float(fee_map["基金托管费"])
            if "销售服务费" in fee_map:
                fund.service_fee = float(fee_map["销售服务费"])

            total = (fund.management_fee or 0) + (fund.custody_fee or 0) + (fund.service_fee or 0)
            fund.fee_rate = round(total, 4)
            results["success"] += 1
        except Exception as e:
            logger.warning(f"获取 {fund.code} 费率失败: {e}")
            results["failed"] += 1

    db.commit()
    return ok(results)


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
    if "code" in update_data and update_data["code"] != fund.code:
        dup = db.query(Fund).filter(Fund.code == update_data["code"], Fund.id != fund_id).first()
        if dup:
            raise HTTPException(status_code=400, detail="基金代码已存在")
    for key, value in update_data.items():
        setattr(fund, key, value)
    db.commit()
    db.refresh(fund)
    return ok(FundResponse.model_validate(fund).model_dump())


@router.get("/{fund_id}/backfill-status")
def fund_backfill_status(fund_id: int):
    status = get_task_status(fund_id)
    return ok(status)


@router.post("/{fund_id}/fetch-fees")
def fetch_fund_fees(fund_id: int, db: Session = Depends(get_db)):
    """从雪球/天天基金获取持有费率（管理费、托管费、销售服务费）"""
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    try:
        import akshare as ak

        pure_code = fund.code.split(".")[0]
        df = ak.fund_individual_detail_info_xq(symbol=pure_code)
        other_fees = df[df["费用类型"] == "其他费用"]

        fee_map: dict[str, str] = {}
        for _, row in other_fees.iterrows():
            fee_map[row["条件或名称"]] = row["费用"]

        if "基金管理费" in fee_map:
            fund.management_fee = float(fee_map["基金管理费"])
        if "基金托管费" in fee_map:
            fund.custody_fee = float(fee_map["基金托管费"])
        if "销售服务费" in fee_map:
            fund.service_fee = float(fee_map["销售服务费"])

        # 同步更新 fee_rate 为持有总费率
        total = (fund.management_fee or 0) + (fund.custody_fee or 0) + (fund.service_fee or 0)
        fund.fee_rate = round(total, 4)

        db.commit()
        db.refresh(fund)
        return ok(FundResponse.model_validate(fund).model_dump())
    except Exception as e:
        logger.error(f"获取基金费率失败 {fund.code}: {e}")
        raise HTTPException(status_code=500, detail=f"获取费率失败: {e}")


@router.delete("/{fund_id}")
def delete_fund(fund_id: int, db: Session = Depends(get_db)):
    fund = db.query(Fund).filter(Fund.id == fund_id).first()
    if not fund:
        raise HTTPException(status_code=404, detail="基金不存在")
    db.delete(fund)
    db.commit()
    return ok({"deleted": True})
