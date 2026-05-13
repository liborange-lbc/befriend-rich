"""
Migration: Add openid column to data tables for user isolation.

Tables:
  - watch_connections:     simple ALTER TABLE ADD COLUMN
  - watch_activities:      simple ALTER TABLE ADD COLUMN
  - injury_records:        simple ALTER TABLE ADD COLUMN
  - portfolio_records:     rebuild (unique constraint change)
  - portfolio_snapshots:   rebuild (unique constraint change)

All existing data is backfilled with the admin openid (first approved user).
Idempotent: skips if openid column already exists.
"""

import os
import sqlite3
import sys

# Default DB path relative to backend/
DB_PATH = os.environ.get("DB_PATH", "data/fundasset.db")


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def get_admin_openid(cursor) -> str:
    """Get the first approved user's openid as admin backfill value."""
    cursor.execute("SELECT openid FROM wechat_users WHERE status='approved' ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row[0]
    # Fallback: first user
    cursor.execute("SELECT openid FROM wechat_users ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else ""


def migrate_simple_table(cursor, table: str, admin_openid: str):
    """Add openid column to a simple table (no constraint changes)."""
    if column_exists(cursor, table, "openid"):
        print(f"  [{table}] openid column already exists, skipping")
        return
    print(f"  [{table}] Adding openid column...")
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN openid VARCHAR(64)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_openid ON {table}(openid)")
    if admin_openid:
        cursor.execute(f"UPDATE {table} SET openid = ?", (admin_openid,))
        count = cursor.rowcount
        print(f"  [{table}] Backfilled {count} rows with admin openid")


def migrate_portfolio_records(cursor, admin_openid: str):
    """Rebuild portfolio_records with new unique constraint including openid."""
    table = "portfolio_records"
    if column_exists(cursor, table, "openid"):
        print(f"  [{table}] openid column already exists, skipping")
        return

    print(f"  [{table}] Rebuilding table with new unique constraint...")

    cursor.execute(f"""
        CREATE TABLE {table}_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid VARCHAR(64),
            fund_id INTEGER NOT NULL,
            record_date DATE NOT NULL,
            amount FLOAT NOT NULL,
            amount_cny FLOAT NOT NULL,
            profit FLOAT,
            weekly_investment FLOAT,
            channel VARCHAR(20) NOT NULL DEFAULT '微众银行',
            FOREIGN KEY (fund_id) REFERENCES funds(id) ON DELETE CASCADE,
            UNIQUE (fund_id, channel, record_date, openid)
        )
    """)

    cursor.execute(f"""
        INSERT INTO {table}_new (id, openid, fund_id, record_date, amount, amount_cny, profit, weekly_investment, channel)
        SELECT id, ?, fund_id, record_date, amount, amount_cny, profit, weekly_investment, channel
        FROM {table}
    """, (admin_openid,))
    count = cursor.rowcount
    print(f"  [{table}] Copied {count} rows")

    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    cursor.execute(f"CREATE INDEX ix_{table}_openid ON {table}(openid)")
    cursor.execute(f"CREATE INDEX ix_{table}_fund_id ON {table}(fund_id)")
    cursor.execute(f"CREATE INDEX ix_{table}_record_date ON {table}(record_date)")


def migrate_portfolio_snapshots(cursor, admin_openid: str):
    """Rebuild portfolio_snapshots with new unique constraint including openid."""
    table = "portfolio_snapshots"
    if column_exists(cursor, table, "openid"):
        print(f"  [{table}] openid column already exists, skipping")
        return

    print(f"  [{table}] Rebuilding table with new unique constraint...")

    cursor.execute(f"""
        CREATE TABLE {table}_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            openid VARCHAR(64),
            snapshot_date DATE NOT NULL,
            total_amount_cny FLOAT NOT NULL,
            model_breakdown TEXT NOT NULL DEFAULT '{{}}',
            UNIQUE (snapshot_date, openid)
        )
    """)

    cursor.execute(f"""
        INSERT INTO {table}_new (id, openid, snapshot_date, total_amount_cny, model_breakdown)
        SELECT id, ?, snapshot_date, total_amount_cny, model_breakdown
        FROM {table}
    """, (admin_openid,))
    count = cursor.rowcount
    print(f"  [{table}] Copied {count} rows")

    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    cursor.execute(f"CREATE INDEX ix_{table}_openid ON {table}(openid)")
    cursor.execute(f"CREATE INDEX ix_{table}_snapshot_date ON {table}(snapshot_date)")


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        admin_openid = get_admin_openid(cursor)
        if not admin_openid:
            print("WARNING: No users found in wechat_users. Backfill openid will be empty.")
        else:
            print(f"Admin openid: {admin_openid[:8]}...")

        # Simple tables
        migrate_simple_table(cursor, "watch_connections", admin_openid)
        migrate_simple_table(cursor, "watch_activities", admin_openid)
        migrate_simple_table(cursor, "injury_records", admin_openid)

        # Tables with constraint changes
        migrate_portfolio_records(cursor, admin_openid)
        migrate_portfolio_snapshots(cursor, admin_openid)

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
