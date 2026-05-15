"""Longbridge OpenAPI portfolio puller.

Pulls current stock positions from Longbridge via their official SDK
and imports them as PortfolioRecords with channel='长桥证券'.

Auth modes (auto-detected):
1. OAuth (preferred): uses persisted client_id + auto-refreshing token
2. API Key (fallback): uses APP_KEY + APP_SECRET + ACCESS_TOKEN from env
"""
import logging
import os
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

CLIENT_ID_FILE = Path.home() / ".longbridge" / "openapi" / "client_id"


def _get_config():
    """Build Longbridge Config. Try OAuth first, fall back to API key."""
    from longbridge.openapi import Config

    # 1. Try OAuth (persisted client_id + auto-refresh token)
    if CLIENT_ID_FILE.exists():
        client_id = CLIENT_ID_FILE.read_text().strip()
        if client_id:
            try:
                from longbridge.openapi import OAuthBuilder
                oauth = OAuthBuilder(client_id).build(lambda url: None)
                logger.info("Longbridge: using OAuth authentication")
                return Config.from_oauth(oauth)
            except Exception as e:
                logger.warning(f"Longbridge OAuth failed, trying API key: {e}")

    # 2. Fall back to API key (from ~/.liborange_personal)
    secrets: dict[str, str] = {}
    secrets_file = os.path.expanduser("~/.liborange_personal")
    try:
        with open(secrets_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    secrets[k.strip()] = v.strip()
    except FileNotFoundError:
        pass

    app_key = secrets.get("LONGBRIDGE_APP_KEY", "")
    app_secret = secrets.get("LONGBRIDGE_APP_SECRET", "")
    access_token = secrets.get("LONGBRIDGE_ACCESS_TOKEN", "")

    if app_key and app_secret and access_token:
        os.environ["LONGBRIDGE_APP_KEY"] = app_key
        os.environ["LONGBRIDGE_APP_SECRET"] = app_secret
        os.environ["LONGBRIDGE_ACCESS_TOKEN"] = access_token
        logger.info("Longbridge: using API key authentication")
        return Config.from_env()

    raise ValueError(
        "长桥未授权。请在本地运行 python scripts/longbridge_oauth.py register && authorize && deploy"
    )


def _fetch_positions_with_quotes(config) -> list[dict]:
    """Fetch positions and enrich with real-time quotes for accurate market value."""
    from longbridge.openapi import QuoteContext, TradeContext

    trade_ctx = TradeContext(config)
    resp = trade_ctx.stock_positions()

    positions = []
    for channel in resp.channels:
        for pos in channel.positions:
            qty = float(pos.quantity)
            if qty <= 0:
                continue
            positions.append({
                "symbol": pos.symbol,
                "symbol_name": pos.symbol_name,
                "quantity": qty,
                "currency": pos.currency,
                "cost_price": float(pos.cost_price) if pos.cost_price else 0,
            })

    if not positions:
        return []

    # Fetch real-time quotes for market value
    symbols = [p["symbol"] for p in positions]
    quote_map: dict[str, float] = {}
    try:
        quote_ctx = QuoteContext(config)
        quotes = quote_ctx.quote(symbols)
        for q in quotes:
            if q.last_done:
                quote_map[q.symbol] = float(q.last_done)
    except Exception as e:
        logger.warning(f"Longbridge: quote fetch failed, using cost_price: {e}")

    for pos in positions:
        price = quote_map.get(pos["symbol"], pos["cost_price"])
        pos["market_value"] = price * pos["quantity"]

    return positions


def pull_longbridge_positions(db: Session) -> ImportResult:
    """Pull current positions from Longbridge and import as portfolio records."""
    config = _get_config()

    positions = _fetch_positions_with_quotes(config)
    if not positions:
        raise ValueError("长桥账户暂无持仓")

    logger.info(f"Longbridge: fetched {len(positions)} positions")

    items: list[dict] = []
    for pos in positions:
        raw_currency = pos["currency"] or ""
        if raw_currency in ("USD", "US"):
            currency = "USD"
        elif raw_currency in ("HKD", "HK"):
            currency = "HKD"
        else:
            currency = "CNY"

        items.append({
            "资产项": pos["symbol_name"],
            "金额(元)": pos["market_value"],
            "币种": currency,
            "基金代码": pos["symbol"],
        })

    today = date.today()
    return import_from_parsed_data(
        db=db,
        items=items,
        file_name=f"longbridge_{today.isoformat()}.api",
        record_date=today,
        source="longbridge_api",
        channel="长桥证券",
    )
