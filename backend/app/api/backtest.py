import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.strategy import BacktestResult, Strategy
from app.response import ok
from app.schemas.strategy import BacktestRequest, BacktestResultResponse
from app.services.backtest.engine import run_backtest

router = APIRouter()


@router.post("/run")
def execute_backtest(body: BacktestRequest, db: Session = Depends(get_db)):
    strategy = db.query(Strategy).filter(Strategy.id == body.strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="策略不存在")

    config = json.loads(strategy.config)
    result = run_backtest(db, body.fund_id, config, body.start_date, body.end_date)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    bt_result = BacktestResult(
        strategy_id=body.strategy_id,
        fund_id=body.fund_id,
        start_date=body.start_date,
        end_date=body.end_date,
        total_return=result["metrics"].get("total_return"),
        annual_return=result["metrics"].get("annual_return"),
        sharpe_ratio=result["metrics"].get("sharpe_ratio"),
        max_drawdown=result["metrics"].get("max_drawdown"),
        volatility=result["metrics"].get("volatility"),
        win_rate=result["metrics"].get("win_rate"),
        profit_loss_ratio=result["metrics"].get("profit_loss_ratio"),
        trade_log=json.dumps(result["trade_log"]),
        equity_curve=json.dumps(result["equity_curve"]),
    )
    db.add(bt_result)
    db.commit()
    db.refresh(bt_result)
    return ok(BacktestResultResponse.model_validate(bt_result).model_dump())


@router.get("/results")
def list_results(strategy_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(BacktestResult)
    if strategy_id:
        query = query.filter(BacktestResult.strategy_id == strategy_id)
    results = query.order_by(BacktestResult.id.desc()).all()
    return ok([BacktestResultResponse.model_validate(r).model_dump() for r in results])


@router.get("/results/{result_id}")
def get_result(result_id: int, db: Session = Depends(get_db)):
    result = db.query(BacktestResult).filter(BacktestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return ok(BacktestResultResponse.model_validate(result).model_dump())
