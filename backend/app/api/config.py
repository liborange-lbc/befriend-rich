from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.config import SystemConfig
from app.response import ok

router = APIRouter()


class ConfigUpdate(BaseModel):
    configs: dict[str, str]


@router.get("")
def list_configs(db: Session = Depends(get_db)):
    rows = db.query(SystemConfig).order_by(SystemConfig.category, SystemConfig.id).all()
    return ok([
        {
            "key": r.key,
            "value": r.value,
            "category": r.category,
            "description": r.description,
        }
        for r in rows
    ])


@router.put("")
def update_configs(body: ConfigUpdate, db: Session = Depends(get_db)):
    updated = 0
    for key, value in body.configs.items():
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
            updated += 1
    db.commit()
    return ok({"updated": updated})
