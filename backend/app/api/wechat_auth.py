import logging
import os

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.wechat_user import WechatUser
from app.response import fail, ok

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    code: str


class ApproveRequest(BaseModel):
    permissions: dict[str, bool]


def _user_dict(user: WechatUser) -> dict:
    return {
        "openid": user.openid,
        "status": user.status,
        "permissions": user.permissions or {},
    }


def _send_feishu_notification(openid: str) -> None:
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")
    if not webhook_url:
        logger.warning("FEISHU_WEBHOOK_URL not configured, skipping notification")
        return

    approve_link = f"https://liborange.asia/api/v1/auth/approve-all?openid={openid}&token={admin_token}"
    text = f"新用户申请: openid={openid}\n审批链接: {approve_link}"

    try:
        httpx.post(
            webhook_url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
    except Exception as e:
        logger.error(f"Failed to send Feishu notification: {e}")


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    appid = os.environ.get("WX_APPID", "")
    secret = os.environ.get("WX_SECRET", "")

    resp = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": appid,
            "secret": secret,
            "js_code": body.code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    wx_data = resp.json()
    openid = wx_data.get("openid")
    if not openid:
        return fail("微信登录失败: " + wx_data.get("errmsg", "unknown"))

    user = db.query(WechatUser).filter(WechatUser.openid == openid).first()
    if user:
        return ok(_user_dict(user))

    user = WechatUser(
        openid=openid,
        status="pending",
        permissions={},
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _send_feishu_notification(openid)

    return ok(_user_dict(user))


@router.get("/check")
def check_auth(openid: str = Query(...), db: Session = Depends(get_db)):
    user = db.query(WechatUser).filter(WechatUser.openid == openid).first()
    if not user:
        return fail("用户不存在")
    return ok(_user_dict(user))


@router.post("/approve")
def approve_user(
    body: ApproveRequest,
    openid: str = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        return fail("无效的管理员令牌")

    user = db.query(WechatUser).filter(WechatUser.openid == openid).first()
    if not user:
        return fail("用户不存在")

    user.status = "approved"
    user.permissions = body.permissions
    db.commit()
    return ok({"approved": True})


@router.post("/approve-all")
def approve_all(
    openid: str = Query(...),
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        return fail("无效的管理员令牌")

    user = db.query(WechatUser).filter(WechatUser.openid == openid).first()
    if not user:
        return fail("用户不存在")

    user.status = "approved"
    user.permissions = {
        "steps": True,
        "portfolio": True,
        "signals": True,
        "nanny": True,
    }
    db.commit()
    return ok({"approved": True})


@router.get("/pending")
def list_pending(token: str = Query(...), db: Session = Depends(get_db)):
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")
    if not admin_token or token != admin_token:
        return fail("无效的管理员令牌")

    users = db.query(WechatUser).filter(WechatUser.status == "pending").all()
    return ok([_user_dict(u) for u in users])
