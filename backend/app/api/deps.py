from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.wechat_user import WechatUser


def get_current_user(
    x_openid: str = Header(..., alias="X-OpenID"),
    db: Session = Depends(get_db),
) -> WechatUser:
    if not x_openid:
        raise HTTPException(status_code=401, detail="缺少 X-OpenID")
    user = db.query(WechatUser).filter(WechatUser.openid == x_openid).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != "approved":
        raise HTTPException(status_code=403, detail="用户未审批通过")
    return user


def get_openid(user: WechatUser = Depends(get_current_user)) -> str:
    return user.openid


def require_permission(perm_key: str):
    def _checker(user: WechatUser = Depends(get_current_user)) -> WechatUser:
        perms = user.permissions or {}
        if not perms.get(perm_key):
            raise HTTPException(status_code=403, detail=f"缺少 {perm_key} 权限")
        return user
    return _checker
