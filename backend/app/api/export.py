"""数据导出 API — CSV 导出 + 投资报告 JSON。"""

import csv
import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.fund import Fund
from app.models.portfolio import PortfolioRecord
from app.response import ok
from app.services.fund_stats_service import get_all_fund_stats
from app.services.return_attribution_service import get_attribution_summary, get_attribution_by_fund

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/portfolio-csv")
def export_portfolio_csv(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """导出持仓记录为 CSV。"""
    q = db.query(PortfolioRecord).order_by(desc(PortfolioRecord.record_date))
    if start_date:
        q = q.filter(PortfolioRecord.record_date >= start_date)
    if end_date:
        q = q.filter(PortfolioRecord.record_date <= end_date)
    records = q.all()

    funds = {f.id: f for f in db.query(Fund).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "基金代码", "基金名称", "渠道", "币种", "金额", "金额(CNY)", "盈亏", "周投入"])

    for r in records:
        fund = funds.get(r.fund_id)
        writer.writerow([
            r.record_date.isoformat(),
            fund.code if fund else "",
            fund.name if fund else "",
            r.channel,
            fund.currency if fund else "CNY",
            r.amount,
            r.amount_cny,
            r.profit or 0,
            r.weekly_investment or 0,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=portfolio_{date.today().isoformat()}.csv"},
    )


@router.get("/fund-stats-csv")
def export_fund_stats_csv(db: Session = Depends(get_db)):
    """导出基金风险指标为 CSV。"""
    stats = get_all_fund_stats(db)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["代码", "名称", "币种", "年化收益", "最大回撤", "波动率", "夏普比率", "近1月", "近3月", "近6月", "近12月"])

    for s in stats:
        writer.writerow([
            s["fund_code"],
            s["fund_name"],
            s["currency"],
            f'{s["annualized_return"]:.4f}' if s["annualized_return"] is not None else "",
            f'{s["max_drawdown"]:.4f}' if s["max_drawdown"] is not None else "",
            f'{s["volatility"]:.4f}' if s["volatility"] is not None else "",
            f'{s["sharpe_ratio"]:.4f}' if s["sharpe_ratio"] is not None else "",
            f'{s["return_1m"]:.4f}' if s["return_1m"] is not None else "",
            f'{s["return_3m"]:.4f}' if s["return_3m"] is not None else "",
            f'{s["return_6m"]:.4f}' if s["return_6m"] is not None else "",
            f'{s["return_12m"]:.4f}' if s["return_12m"] is not None else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=fund_stats_{date.today().isoformat()}.csv"},
    )


@router.get("/report")
def export_investment_report(db: Session = Depends(get_db)):
    """生成投资报告 JSON（前端渲染）。"""
    summary = get_attribution_summary(db)
    by_fund = get_attribution_by_fund(db)
    stats = get_all_fund_stats(db)

    fund_count = db.query(Fund).filter(Fund.is_active == True).count()  # noqa: E712

    return ok({
        "report_date": date.today().isoformat(),
        "overview": {
            "fund_count": fund_count,
            **summary,
        },
        "top_performers": sorted(by_fund, key=lambda x: x.get("return_pct") or -999, reverse=True)[:5],
        "worst_performers": sorted(by_fund, key=lambda x: x.get("return_pct") or 999)[:5],
        "fund_stats": stats,
        "by_fund": by_fund,
    })
