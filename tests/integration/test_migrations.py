import os
import shutil
import sqlite3
import pytest
from flask_migrate import upgrade, stamp
from src.web.app import create_app


def get_rev_001_id(migrations_dir: str) -> str:
    """Find the revision ID for the initial 001 migration."""
    versions_dir = os.path.join(migrations_dir, "versions")
    if not os.path.exists(versions_dir):
        return ""
    for fname in os.listdir(versions_dir):
        if fname.endswith(".py") and "001_initial_schema" in fname:
            return fname.split("_")[0]
    return ""


def test_clean_database_upgrade_from_scratch(tmp_path):
    """Test that applying migrations from scratch creates all tables, columns, and indexes."""
    clean_db = str(tmp_path / "scratch.db")
    app = create_app({"TESTING": True, "DATABASE_PATH": clean_db})
    migrations_dir = os.path.abspath("migrations")

    with app.app_context():
        upgrade(directory=migrations_dir)

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()

    # Verify all tables exist
    tables = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "tasks", "audit_logs", "password_reset_tokens"}.issubset(tables)

    # Verify tasks columns (soft delete)
    task_cols = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()
    }
    assert "is_deleted" in task_cols
    assert "deleted_at" in task_cols

    # Verify password_reset_tokens columns
    token_cols = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(password_reset_tokens)").fetchall()
    }
    assert {"id", "user_id", "token_hash", "expires_at", "used", "created_at"}.issubset(token_cols)

    # Verify indexes
    indexes = {
        row[1]
        for row in cursor.execute(
            "SELECT type, name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_tasks_user_active" in indexes or "idx_tasks_user_created" in indexes
    assert "idx_reset_token_hash" in indexes

    conn.close()


def test_migration_preserves_existing_data(tmp_path):
    """Test that stamping 001 and upgrading to 002 on a copy of taskcontrol.db preserves all data."""
    original_db = "taskcontrol_backup.db" if os.path.exists("taskcontrol_backup.db") else "taskcontrol.db"
    assert os.path.exists(original_db), "Database source must exist to run this test"

    copy_db = str(tmp_path / "taskcontrol_copy.db")
    shutil.copy2(original_db, copy_db)

    # Read pre-migration counts
    conn = sqlite3.connect(copy_db)
    cur = conn.cursor()
    users_before = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    tasks_before = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    logs_before = cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()

    assert users_before == 1
    assert tasks_before == 4
    assert logs_before == 7

    app = create_app({"TESTING": True, "DATABASE_PATH": copy_db})
    migrations_dir = os.path.abspath("migrations")
    rev_001 = get_rev_001_id(migrations_dir)
    assert rev_001, "Revision 001 ID must exist in migrations/versions"

    with app.app_context():
        # Stamp strictly at 001
        stamp(directory=migrations_dir, revision=rev_001)
        # Upgrade to 002
        upgrade(directory=migrations_dir)

    # Verify post-migration preservation
    conn = sqlite3.connect(copy_db)
    cur = conn.cursor()
    assert cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == users_before
    assert cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == tasks_before
    assert cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == logs_before

    # Verify default values for pre-existing tasks
    tasks = cur.execute("SELECT id, is_deleted, deleted_at FROM tasks").fetchall()
    for task_id, is_deleted, deleted_at in tasks:
        assert is_deleted == 0 or is_deleted is False
        assert deleted_at is None

    conn.close()


def test_audit_logs_check_constraint_allows_new_actions(tmp_path):
    """Test that audit_logs in the migrated database allows 'delete' and 'reopen' actions."""
    original_db = "taskcontrol_backup.db" if os.path.exists("taskcontrol_backup.db") else "taskcontrol.db"
    copy_db = str(tmp_path / "audit_test.db")
    shutil.copy2(original_db, copy_db)

    app = create_app({"TESTING": True, "DATABASE_PATH": copy_db})
    migrations_dir = os.path.abspath("migrations")
    rev_001 = get_rev_001_id(migrations_dir)

    with app.app_context():
        stamp(directory=migrations_dir, revision=rev_001)
        upgrade(directory=migrations_dir)

    conn = sqlite3.connect(copy_db)
    cur = conn.cursor()

    # Get valid task and user id
    task_id = cur.execute("SELECT id FROM tasks LIMIT 1").fetchone()[0]
    user_id = cur.execute("SELECT id FROM users LIMIT 1").fetchone()[0]

    # Insert action='delete'
    cur.execute(
        "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, user_id, "delete", '{"reason": "test soft delete"}', "2026-10-04T12:00:00Z"),
    )
    conn.commit()

    # Insert action='reopen'
    cur.execute(
        "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, user_id, "reopen", '{"from": "completada", "to": "pendiente"}', "2026-10-04T12:05:00Z"),
    )
    conn.commit()

    # Verify invalid action fails CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, user_id, "invalid_action", "{}", "2026-10-04T12:10:00Z"),
        )
        conn.commit()

    conn.close()
