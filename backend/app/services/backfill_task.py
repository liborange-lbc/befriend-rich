import logging
import threading
from datetime import date

from app.database import SessionLocal
from app.models.fund import Fund
from app.services.market_data.fetcher import fetch_prices_for_fund

logger = logging.getLogger(__name__)

_tasks: dict[int, dict[str, str]] = {}
_lock = threading.Lock()


def get_task_status(fund_id: int) -> dict[str, str] | None:
    with _lock:
        return _tasks.get(fund_id)


def start_backfill(fund_id: int) -> None:
    with _lock:
        _tasks[fund_id] = {"status": "running", "message": "正在回填历史数据..."}
    thread = threading.Thread(target=_run_backfill, args=(fund_id,), daemon=True)
    thread.start()


def _run_backfill(fund_id: int) -> None:
    db = SessionLocal()
    try:
        fund = db.query(Fund).filter(Fund.id == fund_id).first()
        if not fund:
            with _lock:
                _tasks[fund_id] = {"status": "error", "message": "基金不存在"}
            return
        end = date.today()
        start = date(end.year - 10, end.month, end.day)
        fetch_prices_for_fund(db, fund, start, end)
        with _lock:
            _tasks[fund_id] = {"status": "done", "message": "回填完成"}
    except Exception as e:
        logger.error(f"Backfill failed for fund {fund_id}: {e}")
        with _lock:
            _tasks[fund_id] = {"status": "error", "message": str(e)}
    finally:
        db.close()
