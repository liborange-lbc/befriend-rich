"""Tool definitions for the AI assistant.

Each tool maps to an internal API call executed directly (no HTTP round-trip).
Only read-only operations + a safe config-update allowlist.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.allocation import AllocationSnapshot, AllocationTarget
from app.models.config import SystemConfig
from app.models.fund import Fund
from app.models.guru import GuruHolding, GuruTrade
from app.models.portfolio import PortfolioRecord, PortfolioSnapshot
from app.models.price import ExchangeRate, FundDailyPrice
from app.models.strategy import AlertLog, BacktestResult, Strategy

# Keys the assistant is allowed to modify
SAFE_CONFIG_KEYS = frozenset({
    "backfill_years",
    "exchange_rate_pairs",
    "default_rate_usd_cny",
    "default_rate_hkd_cny",
    "scheduler_market_cron",
    "scheduler_strategy_hours",
})

TOOL_DEFINITIONS = [
    {
        "name": "get_funds",
        "description": "获取所有基金列表，包含代码、名称、币种、数据源、费率等信息",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_fund_prices",
        "description": "获取某只基金的历史价格和均线偏离度数据",
        "input_schema": {
            "type": "object",
            "properties": {
                "fund_id": {"type": "integer", "description": "基金ID"},
                "days": {"type": "integer", "description": "最近N天的数据，默认30", "default": 30},
            },
            "required": ["fund_id"],
        },
    },
    {
        "name": "get_deviation_summary",
        "description": "获取所有活跃基金的最新偏离度汇总（MA30/60/90/120/180/360偏离度）",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_portfolio_latest",
        "description": "获取最新的投资组合持仓记录",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_portfolio_snapshots",
        "description": "获取投资组合历史快照（总资产趋势）",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回最近N条快照，默认20", "default": 20},
            },
            "required": [],
        },
    },
    {
        "name": "get_exchange_rates",
        "description": "获取最近的汇率数据",
        "input_schema": {
            "type": "object",
            "properties": {
                "pair": {"type": "string", "description": "币种对，如 USD/CNY 或 HKD/CNY"},
                "days": {"type": "integer", "description": "最近N天，默认30", "default": 30},
            },
            "required": ["pair"],
        },
    },
    {
        "name": "get_strategies",
        "description": "获取所有策略列表及其配置",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_recent_alerts",
        "description": "获取最近的策略告警日志",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数，默认10", "default": 10},
            },
            "required": [],
        },
    },
    {
        "name": "get_configs",
        "description": "获取系统配置项（不含密钥）",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_config",
        "description": "更新系统配置项（仅限安全配置项：backfill_years, exchange_rate_pairs, default_rate_*, scheduler_*）",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "配置键名"},
                "value": {"type": "string", "description": "新的配置值"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_allocation_model",
        "description": "获取当前良田模型配比目标及偏离度",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "suggest_rebalance",
        "description": "基于当前偏离度生成调仓建议，偏离>3%的类别按优先级排序",
        "input_schema": {
            "type": "object",
            "properties": {
                "total_capital": {"type": "number", "description": "总资金（元），用于计算调仓金额"},
            },
            "required": [],
        },
    },
    {
        "name": "analyze_category_performance",
        "description": "分析某个良田类别的表现（收益率、波动率、夏普、基金明细）",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_name": {"type": "string", "description": "类别名称，如 红利、美股大盘"},
            },
            "required": ["category_name"],
        },
    },
    {
        "name": "get_allocation_deviation",
        "description": "获取投资组合相对良田模型的整体偏离度摘要和健康评分",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compare_vs_benchmark",
        "description": "对比投资组合实际收益与目标收益（10%）",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_guru_signals",
        "description": "获取近期大师买卖信号，与持仓交叉参考",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _serialize(obj: Any) -> Any:
    """Convert SQLAlchemy model to dict, handling date serialization."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, '__dict__'):
        d = {}
        for k, v in obj.__dict__.items():
            if k.startswith('_'):
                continue
            if isinstance(v, date):
                d[k] = v.isoformat()
            elif isinstance(v, (str, int, float, bool, type(None))):
                d[k] = v
            else:
                d[k] = str(v)
        return d
    return obj


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool and return JSON result string."""
    db: Session = SessionLocal()
    try:
        result = _run(db, name, args)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        db.close()


def _run(db: Session, name: str, args: dict[str, Any]) -> Any:
    if name == "get_funds":
        funds = db.query(Fund).all()
        return _serialize(funds)

    if name == "get_fund_prices":
        fund_id = args["fund_id"]
        days = args.get("days", 30)
        prices = (
            db.query(FundDailyPrice)
            .filter(FundDailyPrice.fund_id == fund_id)
            .order_by(FundDailyPrice.date.desc())
            .limit(days)
            .all()
        )
        return _serialize(prices)

    if name == "get_deviation_summary":
        funds = db.query(Fund).filter(Fund.is_active == True).all()
        result = []
        for fund in funds:
            latest = (
                db.query(FundDailyPrice)
                .filter(FundDailyPrice.fund_id == fund.id)
                .order_by(FundDailyPrice.date.desc())
                .first()
            )
            if latest:
                result.append({
                    "fund_id": fund.id, "fund_name": fund.name, "fund_code": fund.code,
                    "date": latest.date.isoformat(), "close_price": latest.close_price,
                    "dev_30": latest.dev_30, "dev_60": latest.dev_60, "dev_90": latest.dev_90,
                    "dev_120": latest.dev_120, "dev_180": latest.dev_180, "dev_360": latest.dev_360,
                })
        return result

    if name == "get_portfolio_latest":
        records = (
            db.query(PortfolioRecord)
            .order_by(PortfolioRecord.record_date.desc())
            .limit(50)
            .all()
        )
        return _serialize(records)

    if name == "get_portfolio_snapshots":
        limit = args.get("limit", 20)
        snapshots = (
            db.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(limit)
            .all()
        )
        return _serialize(snapshots)

    if name == "get_exchange_rates":
        pair = args["pair"]
        days = args.get("days", 30)
        rates = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.pair == pair)
            .order_by(ExchangeRate.date.desc())
            .limit(days)
            .all()
        )
        return _serialize(rates)

    if name == "get_strategies":
        strategies = db.query(Strategy).all()
        return _serialize(strategies)

    if name == "get_recent_alerts":
        limit = args.get("limit", 10)
        alerts = (
            db.query(AlertLog)
            .order_by(AlertLog.triggered_at.desc())
            .limit(limit)
            .all()
        )
        return _serialize(alerts)

    if name == "get_configs":
        configs = db.query(SystemConfig).all()
        # Mask secret values
        result = []
        for c in configs:
            val = c.value
            if c.category == "api" and val:
                val = val[:3] + "***" + val[-2:] if len(val) > 5 else "***"
            result.append({"key": c.key, "value": val, "category": c.category, "description": c.description})
        return result

    if name == "update_config":
        key = args["key"]
        value = args["value"]
        if key not in SAFE_CONFIG_KEYS:
            return {"error": f"不允许修改此配置项: {key}，安全配置项: {', '.join(sorted(SAFE_CONFIG_KEYS))}"}
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if not row:
            return {"error": f"配置项不存在: {key}"}
        row.value = value
        db.commit()
        return {"success": True, "key": key, "value": value}

    if name == "get_allocation_model":
        targets = (
            db.query(AllocationTarget)
            .filter(AllocationTarget.model_id == 1, AllocationTarget.status == "active")
            .all()
        )
        return [
            {
                "category_name": t.category_name,
                "parent_name": t.parent_name,
                "target_weight": t.target_weight,
                "current_weight": t.current_weight,
                "deviation": t.deviation,
                "annual_return": t.annual_return,
                "sharpe_ratio": t.sharpe_ratio,
            }
            for t in targets
        ]

    if name == "suggest_rebalance":
        targets = (
            db.query(AllocationTarget)
            .filter(AllocationTarget.model_id == 1, AllocationTarget.status == "active")
            .all()
        )
        # Get total capital from latest snapshot or from args
        total_capital = args.get("total_capital")
        if not total_capital:
            snap = (
                db.query(AllocationSnapshot)
                .filter(AllocationSnapshot.model_id == 1)
                .order_by(AllocationSnapshot.created_at.desc())
                .first()
            )
            total_capital = snap.total_capital if snap else 0
        deviated = [t for t in targets if abs(t.deviation) > 0.03]
        deviated.sort(key=lambda t: abs(t.deviation), reverse=True)
        suggestions = []
        for t in deviated:
            diff = t.target_weight - t.current_weight
            amount = abs(diff) * total_capital
            action = "加仓" if diff > 0 else "减仓"
            suggestions.append({
                "category_name": t.category_name,
                "action": action,
                "amount": round(amount, 0),
                "deviation": t.deviation,
                "target_weight": t.target_weight,
                "current_weight": t.current_weight,
            })
        return {"total_capital": total_capital, "suggestions": suggestions}

    if name == "analyze_category_performance":
        cat_name = args["category_name"]
        target = (
            db.query(AllocationTarget)
            .filter(
                AllocationTarget.model_id == 1,
                AllocationTarget.status == "active",
                AllocationTarget.category_name == cat_name,
            )
            .first()
        )
        if not target:
            return {"error": f"未找到类别: {cat_name}"}
        # Find funds in this category via PortfolioRecord
        records = (
            db.query(PortfolioRecord)
            .order_by(PortfolioRecord.record_date.desc())
            .limit(100)
            .all()
        )
        # Get recent prices for matched funds
        fund_ids = list({r.fund_id for r in records if r.fund_id})
        recent_prices = []
        for fid in fund_ids[:10]:
            prices = (
                db.query(FundDailyPrice)
                .filter(FundDailyPrice.fund_id == fid)
                .order_by(FundDailyPrice.date.desc())
                .limit(5)
                .all()
            )
            if prices:
                fund = db.query(Fund).filter(Fund.id == fid).first()
                recent_prices.append({
                    "fund_name": fund.name if fund else str(fid),
                    "latest_price": prices[0].close_price,
                    "5d_trend": [p.close_price for p in reversed(prices)],
                })
        return {
            "category_name": cat_name,
            "target_weight": target.target_weight,
            "current_weight": target.current_weight,
            "deviation": target.deviation,
            "annual_return": target.annual_return,
            "volatility": target.volatility,
            "max_drawdown": target.max_drawdown,
            "sharpe_ratio": target.sharpe_ratio,
            "fund_trends": recent_prices,
        }

    if name == "get_allocation_deviation":
        targets = (
            db.query(AllocationTarget)
            .filter(AllocationTarget.model_id == 1, AllocationTarget.status == "active")
            .all()
        )
        if not targets:
            return {"error": "无配比数据"}
        deviations = [abs(t.deviation) for t in targets]
        max_dev = max(deviations) if deviations else 0
        avg_dev = sum(deviations) / len(deviations) if deviations else 0
        # Health score: 100 - penalty for deviations
        health_score = max(0, round(100 - sum(d * 500 for d in deviations if d > 0.03)))
        top_deviations = sorted(targets, key=lambda t: abs(t.deviation), reverse=True)[:5]
        return {
            "health_score": health_score,
            "max_deviation": max_dev,
            "avg_deviation": round(avg_dev, 4),
            "category_count": len(targets),
            "over_threshold_count": sum(1 for d in deviations if d > 0.03),
            "top_deviations": [
                {
                    "category_name": t.category_name,
                    "deviation": t.deviation,
                    "target_weight": t.target_weight,
                    "current_weight": t.current_weight,
                }
                for t in top_deviations
            ],
        }

    if name == "compare_vs_benchmark":
        snapshots = (
            db.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.snapshot_date.desc())
            .limit(30)
            .all()
        )
        if len(snapshots) < 2:
            return {"error": "快照数据不足，无法计算收益"}
        latest = snapshots[0]
        oldest = snapshots[-1]
        days = (latest.snapshot_date - oldest.snapshot_date).days
        if days <= 0:
            return {"error": "快照日期范围不足"}
        actual_return = (latest.total_value - oldest.total_value) / oldest.total_value if oldest.total_value else 0
        annualized = ((1 + actual_return) ** (365 / days) - 1) if days > 0 else 0
        target_return = 0.10
        on_track = annualized >= target_return
        return {
            "period_days": days,
            "period_return": round(actual_return, 4),
            "annualized_return": round(annualized, 4),
            "target_return": target_return,
            "on_track": on_track,
            "latest_total_value": latest.total_value,
        }

    if name == "get_guru_signals":
        trades = (
            db.query(GuruTrade)
            .order_by(GuruTrade.report_date.desc())
            .limit(50)
            .all()
        )
        # Cross-reference with portfolio holdings
        holdings = db.query(PortfolioRecord).order_by(PortfolioRecord.record_date.desc()).limit(50).all()
        held_codes = {r.fund_code for r in holdings if hasattr(r, "fund_code") and r.fund_code}
        signals = []
        for t in trades:
            relevant = t.stock_code in held_codes if t.stock_code else False
            signals.append({
                "guru_id": t.guru_id,
                "stock_code": t.stock_code,
                "stock_name": t.stock_name,
                "action": t.action,
                "value": t.value,
                "trade_date": t.trade_date,
                "report_date": t.report_date,
                "relevant_to_portfolio": relevant,
            })
        return signals

    return {"error": f"Unknown tool: {name}"}
