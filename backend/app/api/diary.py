import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.diary import DiaryEntry
from app.response import ok

logger = logging.getLogger(__name__)

router = APIRouter()


class DiaryCreate(BaseModel):
    entry_date: date
    title: str
    content: str = ""
    mood: str | None = None
    tags: list[str] = []


class DiaryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    mood: str | None = None
    tags: list[str] | None = None


def _to_dict(entry: DiaryEntry) -> dict:
    return {
        "id": entry.id,
        "entry_date": entry.entry_date.isoformat(),
        "title": entry.title,
        "content": entry.content,
        "mood": entry.mood,
        "tags": json.loads(entry.tags) if entry.tags else [],
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


@router.get("")
def list_diary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """列出日记条目。"""
    q = db.query(DiaryEntry)
    if start_date:
        q = q.filter(DiaryEntry.entry_date >= start_date)
    if end_date:
        q = q.filter(DiaryEntry.entry_date <= end_date)
    if keyword:
        q = q.filter(DiaryEntry.title.contains(keyword) | DiaryEntry.content.contains(keyword))
    entries = q.order_by(desc(DiaryEntry.entry_date)).limit(limit).all()
    return ok([_to_dict(e) for e in entries])


@router.post("")
def create_diary(body: DiaryCreate, db: Session = Depends(get_db)):
    """创建日记条目。"""
    entry = DiaryEntry(
        entry_date=body.entry_date,
        title=body.title,
        content=body.content,
        mood=body.mood,
        tags=json.dumps(body.tags, ensure_ascii=False),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return ok(_to_dict(entry))


@router.put("/{entry_id}")
def update_diary(entry_id: int, body: DiaryUpdate, db: Session = Depends(get_db)):
    """更新日记条目。"""
    entry = db.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")

    if body.title is not None:
        entry.title = body.title
    if body.content is not None:
        entry.content = body.content
    if body.mood is not None:
        entry.mood = body.mood
    if body.tags is not None:
        entry.tags = json.dumps(body.tags, ensure_ascii=False)

    db.commit()
    db.refresh(entry)
    return ok(_to_dict(entry))


@router.delete("/{entry_id}")
def delete_diary(entry_id: int, db: Session = Depends(get_db)):
    """删除日记条目。"""
    entry = db.query(DiaryEntry).filter(DiaryEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="日记不存在")
    db.delete(entry)
    db.commit()
    return ok({"deleted": entry_id})


@router.post("/ai-summary")
def ai_summary(
    period: str = Query(default="week", description="week or month"),
    db: Session = Depends(get_db),
):
    """AI 生成投资总结（需要 anthropic_api_key 配置）。"""
    from datetime import timedelta

    from app.services.config_service import get_config_with_db

    api_key = get_config_with_db(db, "anthropic_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="请先配置 Anthropic API Key")

    # Get recent entries
    today = date.today()
    if period == "month":
        start = today.replace(day=1)
        period_label = f"{today.year}年{today.month}月"
    else:
        start = today - timedelta(days=7)
        period_label = f"{start.isoformat()} ~ {today.isoformat()}"

    entries = (
        db.query(DiaryEntry)
        .filter(DiaryEntry.entry_date >= start, DiaryEntry.entry_date <= today)
        .order_by(DiaryEntry.entry_date)
        .all()
    )

    if not entries:
        return ok({"summary": f"{period_label} 期间暂无日记记录。"})

    # Build context
    diary_text = "\n".join([
        f"[{e.entry_date}] {e.title} ({e.mood or '无情绪'})\n{e.content}"
        for e in entries
    ])

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"请基于以下投资日记，生成一份{period_label}的投资总结。包括：主要操作、市场判断、情绪变化、得失反思。用中文，300字以内。\n\n{diary_text}",
            }],
        )
        summary = response.content[0].text
    except Exception as e:
        logger.error(f"AI summary failed: {e}")
        summary = f"AI 总结生成失败: {e}"

    return ok({"summary": summary, "period": period_label, "entry_count": len(entries)})
