from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.guru import Guru, GuruHolding, GuruStock, GuruTrade
from app.response import ok
from app.schemas.guru import (
    GuruBase,
    GuruDetail,
    GuruStockBase,
    HoldingItem,
    TradeItem,
)

router = APIRouter()


# ── Gurus ──


@router.get("/gurus")
def list_gurus(category: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Guru)
    if category:
        query = query.filter(Guru.category == category)
    gurus = query.order_by(Guru.name).all()
    return ok({"gurus": [GuruBase.model_validate(g).model_dump() for g in gurus], "total": len(gurus)})


@router.get("/gurus/{slug}")
def get_guru(slug: str, db: Session = Depends(get_db)):
    guru = db.query(Guru).filter(Guru.slug == slug).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Guru not found")
    return ok(GuruDetail.model_validate(guru).model_dump())


@router.get("/gurus/{slug}/holdings")
def get_guru_holdings(slug: str, db: Session = Depends(get_db)):
    guru = db.query(Guru).filter(Guru.slug == slug).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Guru not found")
    holdings = db.query(GuruHolding).filter(GuruHolding.guru_id == guru.id).all()
    return ok([HoldingItem.model_validate(h).model_dump() for h in holdings])


@router.get("/gurus/{slug}/trades")
def get_guru_trades(slug: str, db: Session = Depends(get_db)):
    guru = db.query(Guru).filter(Guru.slug == slug).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Guru not found")
    trades = db.query(GuruTrade).filter(GuruTrade.guru_id == guru.id).all()
    return ok([TradeItem.model_validate(t).model_dump() for t in trades])


@router.get("/gurus/{slug}/sectors")
def get_guru_sectors(slug: str, db: Session = Depends(get_db)):
    guru = db.query(Guru).filter(Guru.slug == slug).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Guru not found")
    sectors = (
        db.query(GuruHolding.sector, func.count(GuruHolding.id))
        .filter(GuruHolding.guru_id == guru.id, GuruHolding.sector != "")
        .group_by(GuruHolding.sector)
        .order_by(func.count(GuruHolding.id).desc())
        .all()
    )
    return ok([{"sector": s, "count": c} for s, c in sectors])


# ── Stocks ──


@router.get("/stocks")
def list_stocks(q: str | None = None, sector: str | None = None, db: Session = Depends(get_db)):
    query = db.query(GuruStock)
    if q:
        pattern = f"%{q}%"
        query = query.filter(GuruStock.code.ilike(pattern) | GuruStock.name.ilike(pattern))
    if sector:
        query = query.filter(GuruStock.sector == sector)
    stocks = query.order_by(GuruStock.guru_count.desc()).limit(200).all()
    return ok([GuruStockBase.model_validate(s).model_dump() for s in stocks])


@router.get("/stocks/{code}")
def get_stock(code: str, db: Session = Depends(get_db)):
    stock = db.query(GuruStock).filter(GuruStock.code == code).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return ok(GuruStockBase.model_validate(stock).model_dump())


@router.get("/stocks/{code}/gurus")
def get_stock_gurus(code: str, db: Session = Depends(get_db)):
    guru_ids = (
        db.query(GuruHolding.guru_id)
        .filter(GuruHolding.stock_code == code)
        .distinct()
        .all()
    )
    ids = [gid for (gid,) in guru_ids]
    if not ids:
        return ok([])
    gurus = db.query(Guru).filter(Guru.id.in_(ids)).all()
    return ok([GuruBase.model_validate(g).model_dump() for g in gurus])


# ── Search ──


@router.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    pattern = f"%{q}%"
    gurus = (
        db.query(Guru)
        .filter(Guru.name.ilike(pattern) | Guru.slug.ilike(pattern))
        .limit(20)
        .all()
    )
    stocks = (
        db.query(GuruStock)
        .filter(GuruStock.code.ilike(pattern) | GuruStock.name.ilike(pattern))
        .limit(20)
        .all()
    )
    return ok({
        "gurus": [GuruBase.model_validate(g).model_dump() for g in gurus],
        "stocks": [GuruStockBase.model_validate(s).model_dump() for s in stocks],
    })


# ── Stats ──


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    total_gurus = db.query(func.count(Guru.id)).scalar()
    total_holdings = db.query(func.count(GuruHolding.id)).scalar()
    total_stocks = db.query(func.count(GuruStock.id)).scalar()
    top_stocks = db.query(GuruStock).order_by(GuruStock.guru_count.desc()).limit(10).all()
    return ok({
        "total_gurus": total_gurus,
        "total_holdings": total_holdings,
        "total_stocks": total_stocks,
        "top_stocks": [GuruStockBase.model_validate(s).model_dump() for s in top_stocks],
    })


@router.get("/top-stocks")
def top_stocks(limit: int = 20, db: Session = Depends(get_db)):
    stocks = (
        db.query(GuruStock)
        .filter(GuruStock.guru_count > 0)
        .order_by(GuruStock.guru_count.desc())
        .limit(limit)
        .all()
    )
    return ok([GuruStockBase.model_validate(s).model_dump() for s in stocks])


@router.post("/refresh")
def refresh_holdings(db: Session = Depends(get_db)):
    """手动触发从官方披露网站更新持仓数据。"""
    from app.services.guru.updater import update_all_guru_holdings

    result = update_all_guru_holdings(db)
    return ok(result)


@router.get("/sectors")
def sectors(db: Session = Depends(get_db)):
    results = (
        db.query(GuruHolding.sector, func.count(GuruHolding.id))
        .filter(GuruHolding.sector != "", GuruHolding.sector.isnot(None))
        .group_by(GuruHolding.sector)
        .order_by(func.count(GuruHolding.id).desc())
        .all()
    )
    return ok([{"sector": s, "count": c} for s, c in results])
