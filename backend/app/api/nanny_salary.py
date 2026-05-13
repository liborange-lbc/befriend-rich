import json as json_mod
import logging
import os
from datetime import date, timedelta

import httpx
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.database import get_db
from app.models.nanny_salary import NannySalaryConfig, NannySalaryHoliday, NannySalaryLeave
from app.models.wechat_user import WechatUser
from app.response import fail, ok

logger = logging.getLogger(__name__)

router = APIRouter()

_nanny_guard = require_permission("nanny")


class HolidayIn(BaseModel):
    name: str
    start_date: date
    end_date: date
    extra_days: int


class LeaveIn(BaseModel):
    start_date: date
    end_date: date
    reason: str = ""


class ConfigIn(BaseModel):
    start_date: date
    salary_amount: int = 9000
    cycle_days: int = 26


# ── Config ──


@router.get("/config")
def get_config(_user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    cfg = db.query(NannySalaryConfig).first()
    if not cfg:
        return ok(None)
    return ok({
        "id": cfg.id,
        "start_date": cfg.start_date.isoformat(),
        "salary_amount": cfg.salary_amount,
        "cycle_days": cfg.cycle_days,
    })


@router.post("/config")
def save_config(body: ConfigIn, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    cfg = db.query(NannySalaryConfig).first()
    if cfg:
        cfg.start_date = body.start_date
        cfg.salary_amount = body.salary_amount
        cfg.cycle_days = body.cycle_days
    else:
        cfg = NannySalaryConfig(
            start_date=body.start_date,
            salary_amount=body.salary_amount,
            cycle_days=body.cycle_days,
        )
        db.add(cfg)
    db.commit()
    return ok({"id": cfg.id})


# ── Holidays ──


@router.get("/holidays")
def list_holidays(_user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    rows = db.query(NannySalaryHoliday).order_by(NannySalaryHoliday.start_date).all()
    return ok([{
        "id": r.id,
        "name": r.name,
        "start_date": r.start_date.isoformat(),
        "end_date": r.end_date.isoformat(),
        "extra_days": r.extra_days,
    } for r in rows])


@router.post("/holidays")
def add_holiday(body: HolidayIn, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    row = NannySalaryHoliday(
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        extra_days=body.extra_days,
    )
    db.add(row)
    db.commit()
    return ok({"id": row.id})


@router.put("/holidays/{holiday_id}")
def update_holiday(holiday_id: int, body: HolidayIn, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    row = db.query(NannySalaryHoliday).filter(NannySalaryHoliday.id == holiday_id).first()
    if not row:
        return ok(None)
    row.name = body.name
    row.start_date = body.start_date
    row.end_date = body.end_date
    row.extra_days = body.extra_days
    db.commit()
    return ok({"id": row.id})


@router.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    db.query(NannySalaryHoliday).filter(NannySalaryHoliday.id == holiday_id).delete()
    db.commit()
    return ok(None)


# ── Leaves ──


@router.get("/leaves")
def list_leaves(_user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    rows = db.query(NannySalaryLeave).order_by(NannySalaryLeave.start_date).all()
    return ok([{
        "id": r.id,
        "start_date": r.start_date.isoformat(),
        "end_date": r.end_date.isoformat(),
        "reason": r.reason,
    } for r in rows])


@router.post("/leaves")
def add_leave(body: LeaveIn, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    row = NannySalaryLeave(start_date=body.start_date, end_date=body.end_date, reason=body.reason)
    db.add(row)
    db.commit()
    return ok({"id": row.id})


@router.delete("/leaves/{leave_id}")
def delete_leave(leave_id: int, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    db.query(NannySalaryLeave).filter(NannySalaryLeave.id == leave_id).delete()
    db.commit()
    return ok(None)


# ── Calculation ──


def _build_leave_set(leaves) -> set:
    """Expand leave date ranges into a set of individual dates."""
    result = set()
    for lv in leaves:
        d = lv.start_date
        while d <= lv.end_date:
            result.add(d)
            d += timedelta(days=1)
    return result


@router.get("/calculate")
def calculate_pay_dates(count: int = 5, _user: WechatUser = Depends(_nanny_guard), db: Session = Depends(get_db)):
    """Calculate next N pay dates based on config, holidays, and leaves."""
    cfg = db.query(NannySalaryConfig).first()
    if not cfg:
        return ok({"error": "未配置基本信息"})

    holidays = db.query(NannySalaryHoliday).order_by(NannySalaryHoliday.start_date).all()
    leave_rows = db.query(NannySalaryLeave).all()
    leaves = _build_leave_set(leave_rows)

    # Build holiday lookup
    holiday_map: dict[date, int] = {}
    holiday_name_map: dict[date, str] = {}
    for h in holidays:
        d = h.start_date
        while d <= h.end_date:
            holiday_name_map[d] = h.name
            holiday_map[d] = 0
            d += timedelta(days=1)
        holiday_map[h.end_date] = h.extra_days

    results = []
    cycle_start = cfg.start_date

    for _ in range(count):
        accumulated = 0
        current = cycle_start
        pay_date = None
        days_detail = []

        while True:
            if current in leaves:
                days_detail.append({
                    "date": current.isoformat(),
                    "type": "leave",
                    "value": 0,
                    "accumulated": accumulated,
                })
                current += timedelta(days=1)
                continue

            day_value = 1
            extra = 0
            holiday_name = None
            if current in holiday_map:
                extra = holiday_map[current]
                day_value += extra
                holiday_name = holiday_name_map.get(current)

            accumulated += day_value

            detail: dict = {
                "date": current.isoformat(),
                "type": "holiday" if holiday_name else "normal",
                "value": day_value,
                "accumulated": accumulated,
            }
            if holiday_name:
                detail["holiday_name"] = holiday_name
                detail["extra"] = extra
            days_detail.append(detail)

            if accumulated >= cfg.cycle_days:
                pay_date = current
                break

            current += timedelta(days=1)

        results.append({
            "cycle_start": cycle_start.isoformat(),
            "pay_date": pay_date.isoformat(),
            "calendar_days": (pay_date - cycle_start).days + 1,
            "days_detail": days_detail,
        })
        # Next cycle starts the day after pay_date (avoid double-counting)
        cycle_start = pay_date + timedelta(days=1)

    today = date.today()
    total_paid = _count_total_paid(cfg, holidays, leave_rows, today)

    return ok({
        "config": {
            "start_date": cfg.start_date.isoformat(),
            "salary_amount": cfg.salary_amount,
            "cycle_days": cfg.cycle_days,
        },
        "pay_dates": results,
        "total_paid": total_paid,
        "total_amount": total_paid * cfg.salary_amount,
    })


@router.post("/request-access")
def request_nanny_access(user: WechatUser = Depends(get_current_user)):
    """Send Feishu notification to admin requesting nanny permission."""
    perms = user.permissions or {}
    if perms.get("nanny"):
        return ok({"message": "已有权限"})

    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    admin_feishu_id = os.environ.get("FEISHU_ADMIN_OPEN_ID", "")
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")

    if not app_id or not app_secret or not admin_feishu_id:
        return fail("飞书通知未配置")

    grant_link = f"https://liborange.asia/api/v1/auth/grant-permission?openid={user.openid}&perm=nanny&token={admin_token}"

    try:
        token_resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        tenant_token = token_resp.json().get("tenant_access_token")
        if not tenant_token:
            return fail("获取飞书令牌失败")

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "安行 · 权限申请"},
                "template": "orange",
            },
            "elements": [
                {"tag": "markdown", "content": f"**用户申请「士平发薪」访问权限**\n\nOpenID: `{user.openid}`\n昵称: {user.nickname or '未设置'}"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "批准"},
                            "type": "primary",
                            "url": grant_link,
                        }
                    ],
                },
            ],
        }

        httpx.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            headers={"Authorization": f"Bearer {tenant_token}"},
            params={"receive_id_type": "open_id"},
            json={
                "receive_id": admin_feishu_id,
                "msg_type": "interactive",
                "content": json_mod.dumps(card),
            },
            timeout=10,
        )
        logger.info("Nanny access request sent for openid=%s", user.openid)
        return ok({"message": "申请已发送，请等待管理员审批"})
    except Exception as e:
        logger.error("Failed to send nanny access request: %s", e)
        return fail("发送申请失败")


def _count_total_paid(cfg, holidays, leave_rows, today: date) -> int:
    """Count how many complete cycles have been paid up to today."""
    leaves = _build_leave_set(leave_rows)
    holiday_map: dict[date, int] = {}
    for h in holidays:
        d = h.start_date
        while d <= h.end_date:
            holiday_map[d] = 0
            d += timedelta(days=1)
        holiday_map[h.end_date] = h.extra_days

    count = 0
    cycle_start = cfg.start_date

    for _ in range(100):
        accumulated = 0
        current = cycle_start

        while True:
            if current in leaves:
                current += timedelta(days=1)
                continue

            day_value = 1
            if current in holiday_map:
                day_value += holiday_map[current]

            accumulated += day_value

            if accumulated >= cfg.cycle_days:
                if current <= today:
                    count += 1
                    cycle_start = current + timedelta(days=1)
                    break
                else:
                    return count

            current += timedelta(days=1)

    return count
