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
from app.models.config import SystemConfig
from app.models.fund import Fund
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

    return {"error": f"Unknown tool: {name}"}
