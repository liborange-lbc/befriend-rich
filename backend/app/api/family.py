import os
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_openid
from app.database import get_db
from app.models.family import FamilyProfile, InjuryRecord
from app.response import ok

router = APIRouter()

AVATAR_DIR = "data/avatars"


# ──────────── Profile ────────────

class ProfileIn(BaseModel):
    nickname: str | None = None


@router.get("/profile")
def get_profile(openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    profile = db.query(FamilyProfile).filter(FamilyProfile.openid == openid).first()
    if not profile:
        # Migrate: if a legacy profile without openid exists, claim it
        legacy = db.query(FamilyProfile).filter(FamilyProfile.openid.is_(None)).first()
        if legacy:
            legacy.openid = openid
            db.commit()
            profile = legacy
        else:
            return ok({"avatar_url": "", "nickname": ""})
    return ok({"avatar_url": profile.avatar_url or "", "nickname": profile.nickname or ""})


@router.put("/profile")
def update_profile(body: ProfileIn, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    profile = db.query(FamilyProfile).filter(FamilyProfile.openid == openid).first()
    if not profile:
        profile = FamilyProfile(openid=openid)
        db.add(profile)
    if body.nickname is not None:
        profile.nickname = body.nickname
    db.commit()
    return ok({"avatar_url": profile.avatar_url or "", "nickname": profile.nickname or ""})


@router.post("/profile/avatar")
async def upload_avatar(avatar: UploadFile = File(...), openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    os.makedirs(AVATAR_DIR, exist_ok=True)

    ext = os.path.splitext(avatar.filename or "avatar.png")[1] or ".png"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)

    content = await avatar.read()
    with open(filepath, "wb") as f:
        f.write(content)

    avatar_url = f"/static/avatars/{filename}"

    profile = db.query(FamilyProfile).filter(FamilyProfile.openid == openid).first()
    if not profile:
        profile = FamilyProfile(openid=openid, avatar_url=avatar_url)
        db.add(profile)
    else:
        # Delete old avatar file
        if profile.avatar_url:
            old_path = profile.avatar_url.replace("/static/avatars/", AVATAR_DIR + "/")
            if os.path.exists(old_path):
                os.remove(old_path)
        profile.avatar_url = avatar_url
    db.commit()
    return ok({"avatar_url": avatar_url})


# ──────────── Injury Records ────────────

class InjuryIn(BaseModel):
    who: str = "自己"
    title: str
    start_date: str
    end_date: str = ""
    symptoms: str = ""
    treatment: str = ""


@router.get("/injuries")
def get_injuries(openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    rows = db.query(InjuryRecord).filter(InjuryRecord.openid == openid).order_by(InjuryRecord.start_date.desc()).all()
    return ok([
        {
            "id": r.id,
            "who": r.who,
            "title": r.title,
            "start_date": r.start_date,
            "end_date": r.end_date or "",
            "symptoms": r.symptoms or "",
            "treatment": r.treatment or "",
        }
        for r in rows
    ])


@router.post("/injuries")
def create_injury(body: InjuryIn, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    record = InjuryRecord(
        openid=openid,
        who=body.who,
        title=body.title,
        start_date=body.start_date,
        end_date=body.end_date,
        symptoms=body.symptoms,
        treatment=body.treatment,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ok({"id": record.id})


@router.put("/injuries/{record_id}")
def update_injury(record_id: int, body: InjuryIn, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    record = db.query(InjuryRecord).filter(InjuryRecord.id == record_id, InjuryRecord.openid == openid).first()
    if not record:
        return ok(None)
    record.who = body.who
    record.title = body.title
    record.start_date = body.start_date
    record.end_date = body.end_date
    record.symptoms = body.symptoms
    record.treatment = body.treatment
    db.commit()
    return ok({"id": record.id})


@router.delete("/injuries/{record_id}")
def delete_injury(record_id: int, openid: str = Depends(get_openid), db: Session = Depends(get_db)):
    record = db.query(InjuryRecord).filter(InjuryRecord.id == record_id, InjuryRecord.openid == openid).first()
    if record:
        db.delete(record)
        db.commit()
    return ok(None)
