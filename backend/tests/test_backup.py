"""Tests for the database backup feature."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.backup_service import (
    BACKUP_DIR,
    cleanup_old_backups,
    create_backup,
    delete_backup,
    list_backups,
    restore_backup,
)


def _setup_test_db(tmp_path: Path) -> Path:
    """Create a minimal SQLite DB for testing."""
    db_path = tmp_path / "data" / "fundasset.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'hello')")
    conn.commit()
    conn.close()
    return db_path


class TestBackupService:
    def test_create_backup(self, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            result = create_backup()
            assert result["filename"].startswith("fundasset_")
            assert result["filename"].endswith(".db")
            assert result["size"] > 0
            assert (backup_dir / result["filename"]).exists()

            # Verify backup is a valid SQLite DB
            conn = sqlite3.connect(str(backup_dir / result["filename"]))
            rows = conn.execute("SELECT * FROM test").fetchall()
            conn.close()
            assert rows == [(1, "hello")]

    def test_list_backups(self, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            create_backup()
            create_backup()
            backups = list_backups()
            assert len(backups) == 2
            # Should be sorted by time descending
            assert backups[0]["created_at"] >= backups[1]["created_at"]

    def test_delete_backup(self, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            result = create_backup()
            assert delete_backup(result["filename"]) is True
            assert len(list_backups()) == 0

    def test_delete_nonexistent_backup(self, tmp_path):
        backup_dir = tmp_path / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.services.backup_service.BACKUP_DIR", backup_dir):
            assert delete_backup("nonexistent.db") is False

    def test_restore_backup(self, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            result = create_backup()

            # Modify the original DB
            conn = sqlite3.connect(str(db_path))
            conn.execute("INSERT INTO test VALUES (2, 'world')")
            conn.commit()
            conn.close()

            # Restore
            restore_backup(result["filename"])

            # Verify restored DB has original data only
            conn = sqlite3.connect(str(db_path))
            rows = conn.execute("SELECT * FROM test").fetchall()
            conn.close()
            assert rows == [(1, "hello")]

    def test_restore_nonexistent_backup(self, tmp_path):
        backup_dir = tmp_path / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.services.backup_service.BACKUP_DIR", backup_dir):
            try:
                restore_backup("nonexistent.db")
                assert False, "Should have raised"
            except FileNotFoundError:
                pass

    def test_cleanup_old_backups(self, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            for _ in range(5):
                create_backup()
            assert len(list_backups()) == 5

            removed = cleanup_old_backups(retention_count=3)
            assert removed == 2
            assert len(list_backups()) == 3


class TestBackupAPI:
    def test_create_backup_api(self, client, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            resp = client.post("/api/v1/backup/create")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert resp.json()["data"]["filename"].startswith("fundasset_")

    def test_list_backups_api(self, client, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            client.post("/api/v1/backup/create")
            resp = client.get("/api/v1/backup/list")
            assert resp.status_code == 200
            assert len(resp.json()["data"]) == 1

    def test_delete_backup_api(self, client, tmp_path):
        db_path = _setup_test_db(tmp_path)
        backup_dir = tmp_path / "data" / "backups"

        with (
            patch("app.services.backup_service.DB_PATH", db_path),
            patch("app.services.backup_service.BACKUP_DIR", backup_dir),
        ):
            create_resp = client.post("/api/v1/backup/create")
            filename = create_resp.json()["data"]["filename"]

            resp = client.delete(f"/api/v1/backup/{filename}")
            assert resp.status_code == 200
            assert resp.json()["data"]["deleted"] == filename

    def test_delete_nonexistent_api(self, client, tmp_path):
        backup_dir = tmp_path / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        with patch("app.services.backup_service.BACKUP_DIR", backup_dir):
            resp = client.delete("/api/v1/backup/nonexistent.db")
            assert resp.status_code == 404
