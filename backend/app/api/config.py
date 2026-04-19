from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.config import SystemConfig
from app.response import ok

router = APIRouter()

SENSITIVE_KEYS = {"imap_password", "feishu_app_secret", "anthropic_api_key"}
MASKED_VALUE = "******"


class ConfigUpdate(BaseModel):
    configs: dict[str, str]


def _mask_sensitive(config: dict) -> dict:
    """Mask sensitive config values for API response."""
    if config["key"] in SENSITIVE_KEYS:
        return {**config, "value": MASKED_VALUE if config["value"] else ""}
    return config


@router.get("")
def list_configs(db: Session = Depends(get_db)):
    rows = db.query(SystemConfig).order_by(SystemConfig.category, SystemConfig.id).all()
    return ok([
        _mask_sensitive({
            "key": r.key,
            "value": r.value,
            "category": r.category,
            "description": r.description,
        })
        for r in rows
    ])


@router.put("")
def update_configs(body: ConfigUpdate, db: Session = Depends(get_db)):
    updated = 0
    for key, value in body.configs.items():
        # Skip masked values — user did not change them
        if key in SENSITIVE_KEYS and value == MASKED_VALUE:
            continue
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
            updated += 1
    db.commit()
    return ok({"updated": updated})
