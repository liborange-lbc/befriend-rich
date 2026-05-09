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
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    admin_feishu_id = os.environ.get("FEISHU_ADMIN_OPEN_ID", "")
    admin_token = os.environ.get("WX_ADMIN_TOKEN", "")

    if not app_id or not app_secret or not admin_feishu_id:
        logger.warning("Feishu bot credentials or admin open_id not configured")
        return

    approve_link = f"https://liborange.asia/api/v1/auth/approve-all?openid={openid}&token={admin_token}"

    try:
        # Get tenant access token
        token_resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        tenant_token = token_resp.json().get("tenant_access_token")
        if not tenant_token:
            logger.error("Failed to get Feishu tenant token")
            return

        import json as json_mod
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "安行 · 新用户申请"},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": f"**新用户申请访问权限**\n\nOpenID: `{openid}`"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "一键审批通过"},
                            "type": "primary",
                            "url": approve_link,
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
        logger.info(f"Feishu approval notification sent for openid={openid}")
    except Exception as e:
        logger.error(f"Failed to send Feishu notification: {e}")


def _exchange_code_for_openid(code: str) -> str | None:
    """Exchange wx code for openid via jscode2session."""
    appid = os.environ.get("WX_APPID", "")
    secret = os.environ.get("WX_SECRET", "")
    resp = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    return resp.json().get("openid")


@router.post("/check-by-code")
def check_by_code(body: LoginRequest, db: Session = Depends(get_db)):
    """Check if user exists by wx code. Does NOT create user."""
    openid = _exchange_code_for_openid(body.code)
    if not openid:
        return fail("微信登录失败")
    user = db.query(WechatUser).filter(WechatUser.openid == openid).first()
    if not user:
        return fail("用户未注册")
    return ok(_user_dict(user))


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    openid = _exchange_code_for_openid(body.code)
    if not openid:
        return fail("微信登录失败")

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
