import json
import logging

import httpx

from app.services.config_service import get_config

logger = logging.getLogger(__name__)


def send_feishu_card_message(title: str, content: str, chat_id: str | None = None):
    app_id = get_config("feishu_app_id")
    app_secret = get_config("feishu_app_secret")
    webhook_url = get_config("feishu_webhook_url")

    if not app_id or not app_secret:
        logger.warning("Feishu credentials not configured")
        return False

    try:
        token = _get_tenant_access_token(app_id, app_secret)
        if not token:
            return False

        if webhook_url:
            return _send_via_webhook(title, content, webhook_url)

        if not chat_id:
            logger.warning("No chat_id or webhook configured")
            return False

        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": content},
            ],
        }

        resp = httpx.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            },
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Feishu send failed: {e}")
        return False


def _send_via_webhook(title: str, content: str, webhook_url: str) -> bool:
    try:
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": content},
                ],
            },
        }
        resp = httpx.post(webhook_url, json=card, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Feishu webhook failed: {e}")
        return False


def _get_tenant_access_token(app_id: str, app_secret: str) -> str | None:
    try:
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        return data.get("tenant_access_token")
    except Exception as e:
        logger.error(f"Failed to get Feishu token: {e}")
        return None
