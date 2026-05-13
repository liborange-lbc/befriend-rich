"""
Migration: Rename mini-program tables to wechat_ prefix + add openid to wechat_steps.

Table renames:
  watch_connections   → wechat_watch_connections
  watch_activities    → wechat_watch_activities
  family_profiles     → wechat_family_profiles
  injury_records      → wechat_injury_records
  portfolio_records   → wechat_portfolio_records
  portfolio_snapshots → wechat_portfolio_snapshots
  nanny_salary_config → wechat_nanny_salary_config
  nanny_salary_holidays → wechat_nanny_salary_holidays
  nanny_salary_leaves → wechat_nanny_salary_leaves

wechat_steps: add openid column + rebuild for unique constraint (date, openid).

Idempotent: skips if target table already exists.
"""

import os
import sqlite3
import sys

DB_PATH = os.environ.get("DB_PATH", "data/fundasset.db")

RENAMES = [
    ("watch_connections", "wechat_watch_connections"),
    ("watch_activities", "wechat_watch_activities"),
    ("family_profiles", "wechat_family_profiles"),
    ("injury_records", "wechat_injury_records"),
    ("portfolio_records", "wechat_portfolio_records"),
    ("portfolio_snapshots", "wechat_portfolio_snapshots"),
    ("nanny_salary_config", "wechat_nanny_salary_config"),
    ("nanny_salary_holidays", "wechat_nanny_salary_holidays"),
    ("nanny_salary_leaves", "wechat_nanny_salary_leaves"),
]


def table_exists(cursor, name: str) -> bool:
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def get_admin_openid(cursor) -> str:
    cursor.execute("SELECT openid FROM wechat_users WHERE status='approved' ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT openid FROM wechat_users ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else ""


def rename_tables(cursor):
    for old, new in RENAMES:
        if not table_exists(cursor, old):
            if table_exists(cursor, new):
                print(f"  [{old} → {new}] Already renamed, skipping")
            else:
                print(f"  [{old}] Source table not found, skipping")
            continue
        if table_exists(cursor, new):
            print(f"  [{new}] Target already exists, skipping")
            continue
        print(f"  [{old} → {new}] Renaming...")
        cursor.execute(f"ALTER TABLE [{old}] RENAME TO [{new}]")

        # Rename indexes too (SQLite keeps old index names, create new ones)
        cursor.execute(f"PRAGMA index_list([{new}])")
        for idx in cursor.fetchall():
            idx_name = idx[1]
            if old in idx_name:
                # Can't rename indexes in SQLite, but old ones still work
                pass


def migrate_wechat_steps(cursor, admin_openid: str):
    """Add openid column to wechat_steps + rebuild for unique constraint."""
    if not table_exists(cursor, "wechat_steps"):
        print("  [wechat_steps] Table not found, skipping")
        return

    if column_exists(cursor, "wechat_steps", "openid"):
        print("  [wechat_steps] openid column already exists, skipping")
        return

    print("  [wechat_steps] Rebuilding with openid column and new unique constraint...")

    cursor.execute("""
        CREATE TABLE wechat_steps_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid VARCHAR(64),
            date DATE NOT NULL,
            steps INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (date, openid)
        )
    """)

    cursor.execute("""
        INSERT INTO wechat_steps_new (id, openid, date, steps, created_at)
        SELECT id, ?, date, steps, created_at
        FROM wechat_steps
    """, (admin_openid,))
    count = cursor.rowcount
    print(f"  [wechat_steps] Copied {count} rows")

    cursor.execute("DROP TABLE wechat_steps")
    cursor.execute("ALTER TABLE wechat_steps_new RENAME TO wechat_steps")
    cursor.execute("CREATE INDEX ix_wechat_steps_openid ON wechat_steps(openid)")
    cursor.execute("CREATE INDEX ix_wechat_steps_date ON wechat_steps(date)")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        admin_openid = get_admin_openid(cursor)
        if admin_openid:
            print(f"Admin openid: {admin_openid[:8]}...")
        else:
            print("WARNING: No users found")

        print("\n=== Renaming tables ===")
        rename_tables(cursor)

        print("\n=== Migrating wechat_steps ===")
        migrate_wechat_steps(cursor, admin_openid)

        conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\nMigration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
