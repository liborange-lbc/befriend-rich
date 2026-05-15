import logging
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.xunji import XunjiTrainCache
from app.response import ok

logger = logging.getLogger(__name__)

XUNJI_URL = "https://trains.xunjiapp.cn/api_trains_for_llm"

router = APIRouter()


def _get_api_key() -> str:
    import os
    # Try env var first, then file
    key = os.environ.get("XUNJI_API_KEY", "")
    if key:
        return key
    for path in ["/root/.liborange_personal", os.path.expanduser("~/.liborange_personal")]:
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("XUNJI_API_KEY="):
                        return line.split("=", 1)[1]
        except Exception:
            continue
    return ""


def _fetch_and_cache(db: Session, openid: str, datestr: str) -> list[str]:
    """Fetch from XunJi API and cache locally. Returns list of training texts."""
    # Check cache first
    cached = db.query(XunjiTrainCache).filter(
        XunjiTrainCache.openid == openid,
        XunjiTrainCache.date == datestr,
    ).first()
    if cached:
        return cached.get_records()

    # Fetch from API
    api_key = _get_api_key()
    if not api_key:
        return []

    try:
        resp = httpx.post(
            XUNJI_URL,
            json={"datestr": datestr},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        data = resp.json()
    except Exception as e:
        logger.warning(f"XunJi API error for {datestr}: {e}")
        return []

    if not data.get("res"):
        return []

    records = data["res"]

    # Cache
    entry = XunjiTrainCache(
        openid=openid,
        date=datestr,
        raw_json=__import__("json").dumps(records, ensure_ascii=False),
    )
    db.merge(entry)
    db.commit()

    return records


@router.get("/trains")
def get_trains(
    date_str: str = Query(..., alias="date", description="YYYY-MM-DD"),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    records = _fetch_and_cache(db, openid, date_str)
    return ok(records)


@router.get("/trains/range")
def get_trains_range(
    start_date: str = Query(...),
    end_date: str = Query(None),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    if not end_date:
        end_date = date.today().isoformat()

    # Return cached data for the range
    rows = (
        db.query(XunjiTrainCache)
        .filter(
            XunjiTrainCache.openid == openid,
            XunjiTrainCache.date >= start_date,
            XunjiTrainCache.date <= end_date,
        )
        .order_by(desc(XunjiTrainCache.date))
        .all()
    )
    result = []
    for r in rows:
        records = r.get_records()
        if records:
            result.append({"date": r.date, "records": records})
    return ok(result)


@router.post("/sync")
def sync_trains(
    days: int = Query(30, ge=1, le=3650),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    """Sync recent training data from XunJi. Skips dates already cached."""
    import time as _time

    today = date.today()
    synced = 0
    skipped = 0
    errors = []

    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        # Skip if cached
        cached = db.query(XunjiTrainCache).filter(
            XunjiTrainCache.openid == openid,
            XunjiTrainCache.date == d,
        ).first()
        if cached:
            skipped += 1
            continue

        try:
            records = _fetch_and_cache(db, openid, d)
            if records:
                synced += 1
        except Exception as e:
            err_msg = str(e)
            if "too frequent" in err_msg.lower() or "retry" in err_msg.lower():
                _time.sleep(91)
                try:
                    records = _fetch_and_cache(db, openid, d)
                    if records:
                        synced += 1
                except Exception as e2:
                    errors.append(f"{d}: {e2}")
            else:
                errors.append(f"{d}: {e}")

    return ok({"synced": synced, "skipped": skipped, "errors": errors})
