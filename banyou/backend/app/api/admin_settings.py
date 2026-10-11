"""管理后台：应用设置 / 素材上传 / 数据概览。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.config import settings as app_settings
from app.database import get_db
from app.models.admin import AdminUser
from app.models.content import ScenicArea, Spot, TourRoute
from app.services import settings_service

router = APIRouter(dependencies=[Depends(require_admin)])

_ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_ALLOWED_AUDIO = {".mp3", ".m4a", ".aac", ".wav", ".ogg"}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return {"items": settings_service.get_all(db)}


@router.put("/settings")
def put_settings(values: dict[str, str], db: Session = Depends(get_db)):
    settings_service.update_many(db, values)
    return {"ok": True}


@router.post("/uploads")
async def upload(file: UploadFile, db: Session = Depends(get_db)):
    """素材上传：图片/音频，落盘 uploads/ 并返回可直接填入表单的 URL。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix in _ALLOWED_IMAGE:
        folder = "images"
    elif suffix in _ALLOWED_AUDIO:
        folder = "audio"
    else:
        raise HTTPException(400, f"不支持的文件类型 {suffix}，仅支持图片/音频")
    target_dir = Path(app_settings.upload_dir) / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{suffix}"
    payload = await file.read()
    if len(payload) > 20 * 1024 * 1024:
        raise HTTPException(400, "文件超过 20MB 限制")
    (target_dir / name).write_bytes(payload)
    return {"url": f"/uploads/{folder}/{name}", "size": len(payload)}


@router.get("/stats")
def stats(admin: AdminUser = Depends(require_admin), db: Session = Depends(get_db)):
    """概览数据：内容规模 + 最近更新提示。"""
    return {
        "admin": {"username": admin.username, "display_name": admin.display_name},
        "scenic_areas": db.query(ScenicArea).count(),
        "spots": db.query(Spot).count(),
        "routes": db.query(TourRoute).count(),
    }
