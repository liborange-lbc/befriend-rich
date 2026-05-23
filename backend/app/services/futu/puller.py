"""富途牛牛持仓拉取。

通过 futu-api SDK 连接本地 OpenD 网关获取持仓数据，
导入为 PortfolioRecords，channel='富途牛牛'。

OpenD 需在宿主机上独立运行（非 Docker 内），
容器通过 host.docker.internal 或宿主机 IP 连接。
"""
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.services.webank.importer import ImportResult, import_from_parsed_data

logger = logging.getLogger(__name__)

# OpenD 连接地址（Docker 容器内访问宿主机）
OPEND_HOST = "172.17.0.1"  # Docker bridge gateway，兼容性最好
OPEND_PORT = 11111


def pull_futu_positions(db: Session) -> ImportResult:
    """从富途 OpenD 拉取当前持仓并导入。"""
    from futu import (
        OpenQuoteContext,
        OpenSecTradeContext,
        RET_OK,
        TrdEnv,
        TrdMarket,
    )

    # 1. 检查 OpenD 连通性
    quote_ctx = OpenQuoteContext(host=OPEND_HOST, port=OPEND_PORT)
    try:
        ret, state = quote_ctx.get_global_state()
        if ret != RET_OK:
            raise ValueError(f"OpenD 连接失败: {state}")
        logger.info(f"Futu OpenD connected, market: {state}")
    finally:
        quote_ctx.close()

    # 2. 查询持仓（真实环境，所有市场）
    trd_ctx = OpenSecTradeContext(host=OPEND_HOST, port=OPEND_PORT)
    try:
        all_positions = []

        for market, market_name in [
            (TrdMarket.US, "US"),
            (TrdMarket.HK, "HK"),
            (TrdMarket.CN, "CN"),
        ]:
            try:
                trd_ctx.unlock_trade(password="")  # 查询不需要交易密码
            except Exception:
                pass

            ret, data = trd_ctx.position_list_query(
                trd_env=TrdEnv.REAL,
                filter_trdmarket=market,
            )
            if ret != RET_OK:
                logger.warning(f"Futu position query failed for {market_name}: {data}")
                continue

            if data is None or data.empty:
                continue

            for _, row in data.iterrows():
                qty = float(row.get("qty", 0))
                if qty <= 0:
                    continue

                market_val = float(row.get("market_val", 0))
                if market_val <= 0:
                    # fallback: nominal_price * qty
                    price = float(row.get("nominal_price", 0))
                    market_val = price * qty

                all_positions.append({
                    "code": str(row.get("code", "")),
                    "name": str(row.get("stock_name", "")),
                    "qty": qty,
                    "market_val": market_val,
                    "currency": str(row.get("currency", "HKD")),
                    "pl_val": float(row.get("pl_val", 0)),
                    "market": market_name,
                })

        if not all_positions:
            raise ValueError("富途账户暂无持仓")

        logger.info(f"Futu: fetched {len(all_positions)} positions")

    finally:
        trd_ctx.close()

    # 3. 构造导入数据
    items: list[dict] = []
    for pos in all_positions:
        raw_currency = pos["currency"]
        if raw_currency in ("USD", "US"):
            currency = "USD"
        elif raw_currency in ("HKD", "HK"):
            currency = "HKD"
        else:
            currency = "CNY"

        items.append({
            "资产项": pos["name"],
            "金额(元)": pos["market_val"],
            "币种": currency,
            "基金代码": pos["code"],
        })

    today = date.today()
    return import_from_parsed_data(
        db=db,
        items=items,
        file_name=f"futu_{today.isoformat()}.api",
        record_date=today,
        source="futu_api",
        channel="富途牛牛",
    )
