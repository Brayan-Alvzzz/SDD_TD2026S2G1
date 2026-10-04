import pytest
import sqlalchemy as sa
from src.infrastructure.models import UserORM, TaskORM, AuditLogORM


def test_sqlite_foreign_keys_pragma_enabled(db_session):
    """Verify that PRAGMA foreign_keys is strictly enabled (1) on the active SQLAlchemy session."""
    fk_status = db_session.execute(sa.text("PRAGMA foreign_keys;")).scalar()
    assert fk_status == 1, f"Expected PRAGMA foreign_keys == 1, got {fk_status}"


def test_invalid_foreign_key_rejected_on_task_creation(db_session):
    """Verify that inserting a task referencing a nonexistent user_id raises IntegrityError."""
    orphan_task = TaskORM(
        user_id=99999,
        title="Orphan Task",
        description="This task points to a nonexistent user",
        due_date=None,
        status="pendiente",
        created_at="2026-10-04T12:00:00Z",
        updated_at="2026-10-04T12:00:00Z"
    )
    db_session.add(orphan_task)

    with pytest.raises(sa.exc.IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_invalid_foreign_key_rejected_on_audit_log_creation(db_session, user_service):
    """Verify that inserting an audit log referencing a nonexistent task_id raises IntegrityError."""
    user = user_service.register_user("fk_audit_test@example.com", "password123")

    orphan_audit = AuditLogORM(
        task_id=99999,
        actor_id=user.id,
        action="create",
        details='{"title": "Nonexistent Task"}',
        created_at="2026-10-04T12:00:00Z"
    )
    db_session.add(orphan_audit)

    with pytest.raises(sa.exc.IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_foreign_keys_reactivated_even_if_migration_fails(tmp_path):
    """Verify that PRAGMA foreign_keys is restored to 1 even if a migration fails."""
    import os
    from unittest import mock
    from flask_migrate import upgrade
    from src.web.app import create_app
    from src.infrastructure.database import db

    temp_db = str(tmp_path / "fk_fail_test.db")
    app = create_app({"TESTING": True, "DATABASE_PATH": temp_db})
    migrations_dir = os.path.abspath("migrations")

    with app.app_context():
        # Normal initial upgrade
        upgrade(directory=migrations_dir)
        with db.engine.connect() as conn:
            assert conn.connection.dbapi_connection.execute("PRAGMA foreign_keys;").fetchone()[0] == 1

        # Simulate failure during a migration run
        with mock.patch("alembic.context.run_migrations", side_effect=RuntimeError("Simulated failure")):
            try:
                upgrade(directory=migrations_dir)
            except BaseException:
                pass

        # Verify foreign keys are strictly re-enabled by the finally block
        with db.engine.connect() as conn:
            fk_after = conn.connection.dbapi_connection.execute("PRAGMA foreign_keys;").fetchone()[0]
            assert fk_after == 1, f"Expected PRAGMA foreign_keys == 1 after failure, got {fk_after}"
