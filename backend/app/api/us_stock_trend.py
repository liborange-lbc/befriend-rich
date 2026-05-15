"""美股趋势 API — 交易额 Top30 榜单 + 趋势分析"""

import logging
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.response import ok
from app.services.us_stock_trend import fetch_and_store_top30, get_ranking_with_analysis

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ranking")
def get_us_stock_ranking(db: Session = Depends(get_db)) -> dict:
    """获取最新美股交易额 Top30 榜单及趋势分析。"""
    result = get_ranking_with_analysis(db)
    return ok(result)


@router.post("/refresh")
def post_refresh_us_stock(db: Session = Depends(get_db)) -> dict:
    """手动触发美股数据刷新。"""
    def _refresh():
        s = SessionLocal()
        try:
            fetch_and_store_top30(s)
        except Exception as e:
            logger.error(f"US stock trend refresh failed: {e}")
        finally:
            s.close()

    threading.Thread(target=_refresh, daemon=True).start()
    return ok({"message": "刷新已开始，请稍后查看"})
