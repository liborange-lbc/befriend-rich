import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.wechat_steps import WechatStep
from app.response import ok

router = APIRouter()

STEP_GOAL = 10000


class StepItem(BaseModel):
    date: date
    steps: int


class SyncRequest(BaseModel):
    steps: list[StepItem]


class SyncEncryptedRequest(BaseModel):
    code: str
    encryptedData: str
    iv: str


@router.post("/sync-encrypted")
def sync_encrypted(body: SyncEncryptedRequest, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    import base64
    import json

    import requests
    from Crypto.Cipher import AES

    appid = os.environ.get("WX_APPID", "")
    secret = os.environ.get("WX_SECRET", "")

    # Exchange code for session_key
    wx_resp = requests.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": appid,
            "secret": secret,
            "js_code": body.code,
            "grant_type": "authorization_code",
        },
    )
    wx_data = wx_resp.json()
    session_key = wx_data.get("session_key")
    if not session_key:
        return ok({"synced": 0, "error": "session_key获取失败"})

    # Decrypt AES-128-CBC
    session_key_bytes = base64.b64decode(session_key)
    iv_bytes = base64.b64decode(body.iv)
    encrypted_bytes = base64.b64decode(body.encryptedData)

    cipher = AES.new(session_key_bytes, AES.MODE_CBC, iv_bytes)
    decrypted = cipher.decrypt(encrypted_bytes)
    # Remove PKCS7 padding
    pad = decrypted[-1]
    decrypted = decrypted[:-pad]

    step_data = json.loads(decrypted.decode("utf-8"))
    step_list = step_data.get("stepInfoList", [])

    count = 0
    for item in step_list:
        ts = item.get("timestamp", 0)
        steps = item.get("step", 0)
        step_date = date.fromtimestamp(ts)
        # Only save up to yesterday (today is incomplete)
        if step_date >= date.today():
            continue
        existing = db.query(WechatStep).filter(WechatStep.date == step_date, WechatStep.openid == openid).first()
        if existing:
            existing.steps = steps
        else:
            db.add(WechatStep(openid=openid, date=step_date, steps=steps))
        count += 1
    db.commit()
    return ok({"synced": count})


@router.post("/sync")
def sync_steps(body: SyncRequest, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    count = 0
    for item in body.steps:
        existing = db.query(WechatStep).filter(WechatStep.date == item.date, WechatStep.openid == openid).first()
        if existing:
            existing.steps = item.steps
        else:
            db.add(WechatStep(openid=openid, date=item.date, steps=item.steps))
        count += 1
    db.commit()
    return ok({"synced": count})


@router.get("/history")
def get_history(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    openid: str = Depends(get_openid),
    db: Session = Depends(get_db),
):
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    rows = (
        db.query(WechatStep)
        .filter(WechatStep.openid == openid, WechatStep.date >= start_date, WechatStep.date <= end_date)
        .order_by(WechatStep.date)
        .all()
    )
    return ok([{"date": str(r.date), "steps": r.steps} for r in rows])


@router.get("/stats")
def get_stats(days: int = Query(30), openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = db.query(WechatStep).filter(WechatStep.openid == openid, WechatStep.date >= since).all()

    if not rows:
        return ok({
            "avg_daily": 0,
            "max_steps": 0,
            "max_date": None,
            "total": 0,
            "achievement_days": 0,
            "goal": STEP_GOAL,
        })

    total = sum(r.steps for r in rows)
    max_row = max(rows, key=lambda r: r.steps)
    achievement_days = sum(1 for r in rows if r.steps >= STEP_GOAL)

    return ok({
        "avg_daily": total // len(rows),
        "max_steps": max_row.steps,
        "max_date": str(max_row.date),
        "total": total,
        "achievement_days": achievement_days,
        "goal": STEP_GOAL,
    })
