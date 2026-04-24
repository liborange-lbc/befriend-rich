import logging

from fastapi import APIRouter, HTTPException, Query

from app.response import ok
from app.services.backup_service import (
    cleanup_old_backups,
    create_backup,
    delete_backup,
    list_backups,
    restore_backup,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/create")
def api_create_backup():
    """手动触发数据库备份。"""
    try:
        result = create_backup()
        cleanup_old_backups(30)
        return ok(result)
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")


@router.get("/list")
def api_list_backups():
    """列出所有备份文件。"""
    return ok(list_backups())


@router.post("/restore")
def api_restore_backup(filename: str = Query(..., description="备份文件名")):
    """从指定备份恢复数据库。需要重启服务生效。"""
    try:
        result = restore_backup(filename)
        return ok(result, meta={"warning": "请重启服务以使恢复生效"})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{filename}")
def api_delete_backup(filename: str):
    """删除指定备份文件。"""
    if not delete_backup(filename):
        raise HTTPException(status_code=404, detail="备份文件不存在")
    return ok({"deleted": filename})
