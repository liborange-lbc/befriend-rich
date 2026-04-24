import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("data/backups")
DB_PATH = Path("data/fundasset.db")


def _ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def create_backup() -> dict:
    """Create a consistent SQLite backup using VACUUM INTO."""
    _ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"fundasset_{timestamp}.db"
    backup_path = BACKUP_DIR / filename

    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(f"VACUUM INTO '{backup_path}'")
    finally:
        conn.close()

    size = backup_path.stat().st_size
    logger.info(f"Backup created: {filename} ({size} bytes)")
    return {
        "filename": filename,
        "size": size,
        "created_at": datetime.now().isoformat(),
    }


def list_backups() -> list[dict]:
    """List all backup files sorted by time descending."""
    _ensure_backup_dir()
    backups = []
    for f in sorted(BACKUP_DIR.glob("fundasset_*.db"), reverse=True):
        stat = f.stat()
        backups.append({
            "filename": f.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return backups


def delete_backup(filename: str) -> bool:
    """Delete a specific backup file. Returns True if deleted."""
    path = BACKUP_DIR / filename
    if not path.exists() or not path.name.startswith("fundasset_"):
        return False
    path.unlink()
    logger.info(f"Backup deleted: {filename}")
    return True


def restore_backup(filename: str) -> dict:
    """Restore database from a backup file.

    This replaces the main DB file. The caller must ensure the app
    is aware that a restart may be needed.
    """
    backup_path = BACKUP_DIR / filename
    if not backup_path.exists() or not backup_path.name.startswith("fundasset_"):
        raise FileNotFoundError(f"Backup not found: {filename}")

    # Verify the backup is a valid SQLite database
    conn = sqlite3.connect(str(backup_path))
    try:
        conn.execute("SELECT count(*) FROM sqlite_master")
    except sqlite3.DatabaseError as e:
        raise ValueError(f"Invalid backup file: {e}")
    finally:
        conn.close()

    # Remove WAL/SHM files before overwrite
    for ext in (".db-wal", ".db-shm"):
        wal = DB_PATH.with_suffix(ext)
        if wal.exists():
            wal.unlink()

    shutil.copy2(str(backup_path), str(DB_PATH))
    logger.info(f"Database restored from: {filename}")
    return {"filename": filename, "restored_at": datetime.now().isoformat()}


def cleanup_old_backups(retention_count: int = 30) -> int:
    """Remove oldest backups beyond retention count. Returns count removed."""
    backups = sorted(BACKUP_DIR.glob("fundasset_*.db"), reverse=True)
    removed = 0
    for f in backups[retention_count:]:
        f.unlink()
        removed += 1
    if removed:
        logger.info(f"Cleaned up {removed} old backups (retention={retention_count})")
    return removed
