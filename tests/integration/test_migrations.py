import os
import shutil
import sqlite3
import pytest
from flask_migrate import upgrade, stamp
from src.web.app import create_app


def get_rev_id(migrations_dir: str, pattern: str) -> str:
    """Find the revision ID matching a pattern in migrations/versions."""
    versions_dir = os.path.join(migrations_dir, "versions")
    if not os.path.exists(versions_dir):
        return ""
    for fname in os.listdir(versions_dir):
        if fname.endswith(".py") and pattern in fname:
            return fname.split("_")[0]
    return ""


def test_clean_database_upgrade_from_scratch(tmp_path):
    """Test that applying migrations from scratch creates all tables, columns, and indexes through revision 003."""
    clean_db = str(tmp_path / "scratch.db")
    app = create_app({"TESTING": True, "DATABASE_PATH": clean_db})
    migrations_dir = os.path.abspath("migrations")

    with app.app_context():
        upgrade(directory=migrations_dir)

    conn = sqlite3.connect(clean_db)
    cursor = conn.cursor()

    # Verify all tables exist, including categories
    tables = {
        row[0]
        for row in cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "tasks", "audit_logs", "password_reset_tokens", "categories"}.issubset(tables)

    # Verify tasks columns (soft delete and Increment 3 additions: priority, category_id)
    task_cols = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()
    }
    assert "is_deleted" in task_cols
    assert "deleted_at" in task_cols
    assert "priority" in task_cols
    assert "category_id" in task_cols

    # Verify categories columns
    category_cols = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(categories)").fetchall()
    }
    assert {"id", "user_id", "name", "created_at"}.issubset(category_cols)

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
    assert "idx_tasks_user_priority" in indexes
    assert "idx_tasks_user_category" in indexes
    assert "idx_categories_user_id" in indexes or "uq_categories_user_name" in indexes
    assert "idx_reset_token_hash" in indexes

    conn.close()


def test_migration_preserves_existing_data(tmp_path):
    """Test that upgrading to head on a temporary copy preserves all data with dynamic count comparison."""
    original_db = "taskcontrol_backup.db" if os.path.exists("taskcontrol_backup.db") else "taskcontrol.db"
    assert os.path.exists(original_db), "Database source must exist to run this test"

    copy_db = str(tmp_path / "taskcontrol_copy.db")
    shutil.copy2(original_db, copy_db)

    # Read pre-migration dynamic counts
    conn = sqlite3.connect(copy_db)
    cur = conn.cursor()
    users_before = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    tasks_before = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    logs_before = cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()

    assert users_before > 0
    assert tasks_before > 0
    assert logs_before > 0

    app = create_app({"TESTING": True, "DATABASE_PATH": copy_db})
    migrations_dir = os.path.abspath("migrations")

    # If unstamped (e.g. from pre-Alembic backup), stamp at 001 first
    conn = sqlite3.connect(copy_db)
    has_alembic = conn.cursor().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
    ).fetchone()
    conn.close()

    with app.app_context():
        if not has_alembic:
            rev_001 = get_rev_id(migrations_dir, "001_initial_schema")
            stamp(directory=migrations_dir, revision=rev_001)
        # Upgrade to head (includes revision 003)
        upgrade(directory=migrations_dir)

    # Verify post-migration preservation with dynamic counts
    conn = sqlite3.connect(copy_db)
    cur = conn.cursor()
    assert cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == users_before
    assert cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == tasks_before
    assert cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == logs_before

    # Verify default values for pre-existing tasks: priority='media', category_id=NULL
    tasks = cur.execute("SELECT id, is_deleted, priority, category_id FROM tasks").fetchall()
    for task_id, is_deleted, priority, category_id in tasks:
        assert priority == "media"
        assert category_id is None

    conn.close()


def test_migration_003_preserves_existing_tasks_with_default_priority(tmp_path):
    """Test that migration 003 assigns priority='media' and category_id=NULL to existing fixture tasks."""
    fixture_db = str(tmp_path / "fixture_v002.db")
    app = create_app({"TESTING": True, "DATABASE_PATH": fixture_db})
    migrations_dir = os.path.abspath("migrations")
    rev_002 = get_rev_id(migrations_dir, "002_task_lifecycle_recovery")
    assert rev_002, "Revision 002 must exist"

    with app.app_context():
        # Upgrade up to 002
        upgrade(directory=migrations_dir, revision=rev_002)

    # Insert fixture data at revision 002 schema
    conn = sqlite3.connect(fixture_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        ("fixture_user@example.com", "hash123", "2026-10-04T10:00:00Z"),
    )
    user_id = cur.lastrowid
    cur.execute(
        "INSERT INTO tasks (user_id, title, description, due_date, status, is_deleted, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, "Fixture Task 1", "Description 1", "2026-10-10", "pendiente", 0, "2026-10-04T10:05:00Z", "2026-10-04T10:05:00Z"),
    )
    cur.execute(
        "INSERT INTO tasks (user_id, title, description, due_date, status, is_deleted, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, "Fixture Task 2", "Description 2", "2026-10-11", "en_progreso", 0, "2026-10-04T10:10:00Z", "2026-10-04T10:10:00Z"),
    )
    cur.execute(
        "INSERT INTO tasks (user_id, title, description, due_date, status, is_deleted, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, "Fixture Task 3", "Description 3", "2026-10-12", "completada", 0, "2026-10-04T10:15:00Z", "2026-10-04T10:15:00Z"),
    )
    cur.execute(
        "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (1, user_id, "create", '{"title": "Fixture Task 1"}', "2026-10-04T10:05:00Z"),
    )
    conn.commit()

    # Pre-migration dynamic counts
    users_before = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    tasks_before = cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    logs_before = cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    conn.close()

    assert users_before == 1
    assert tasks_before == 3
    assert logs_before == 1

    # Now upgrade to head (revision 003)
    with app.app_context():
        upgrade(directory=migrations_dir)

    # Post-migration assertions
    conn = sqlite3.connect(fixture_db)
    cur = conn.cursor()
    assert cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == users_before
    assert cur.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == tasks_before
    assert cur.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == logs_before

    tasks = cur.execute("SELECT id, title, priority, category_id FROM tasks").fetchall()
    assert len(tasks) == 3
    for t_id, title, priority, category_id in tasks:
        assert priority == "media", f"Task {t_id} should have default priority 'media'"
        assert category_id is None, f"Task {t_id} should have category_id NULL"

    conn.close()


def test_migration_003_audit_logs_check_constraint_allows_new_actions(tmp_path):
    """Test that audit_logs in revision 003 allows priority_change and category_change."""
    test_db = str(tmp_path / "audit_test_003.db")
    app = create_app({"TESTING": True, "DATABASE_PATH": test_db})
    migrations_dir = os.path.abspath("migrations")

    with app.app_context():
        upgrade(directory=migrations_dir)

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
        ("audit_user@example.com", "hash456", "2026-10-04T11:00:00Z"),
    )
    user_id = cur.lastrowid

    cur.execute(
        "INSERT INTO tasks (user_id, title, priority, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, "Test Audit Task", "media", "pendiente", "2026-10-04T11:05:00Z", "2026-10-04T11:05:00Z"),
    )
    task_id = cur.lastrowid
    conn.commit()

    # All 7 valid actions
    valid_actions = [
        "create",
        "update",
        "status_change",
        "delete",
        "reopen",
        "priority_change",
        "category_change",
    ]

    for action in valid_actions:
        cur.execute(
            "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, user_id, action, f'{{"action": "{action}"}}', "2026-10-04T11:10:00Z"),
        )
    conn.commit()

    count = cur.execute("SELECT COUNT(*) FROM audit_logs WHERE task_id = ?", (task_id,)).fetchone()[0]
    assert count == len(valid_actions)

    # Verify invalid action fails CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, user_id, "invalid_action_forbidden", "{}", "2026-10-04T11:15:00Z"),
        )
        conn.commit()

    conn.close()
