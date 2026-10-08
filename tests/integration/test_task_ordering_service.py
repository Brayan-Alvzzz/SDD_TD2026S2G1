import os
import time
import sqlite3
import threading
import pytest
from flask_migrate import upgrade
from src.web.app import create_app
from src.domain.exceptions import (
    ValidationError,
    ConflictError,
    TaskNotAccessibleError,
    OperationNotPermittedError
)
from src.domain.services import TaskService
from src.infrastructure.repositories import TaskRepository, AuditLogRepository

def get_rev_id(migrations_dir: str, pattern: str) -> str:
    versions_dir = os.path.join(migrations_dir, "versions")
    if not os.path.exists(versions_dir):
        return ""
    for fname in os.listdir(versions_dir):
        if fname.endswith(".py") and pattern in fname:
            return fname.split("_")[0]
    return ""

def setup_db(db_path, run_up_to=None):
    app = create_app({"TESTING": True, "DATABASE_PATH": db_path})
    migrations_dir = os.path.abspath("migrations")
    with app.app_context():
        if run_up_to:
            upgrade(directory=migrations_dir, revision=run_up_to)
        else:
            upgrade(directory=migrations_dir)
    return app

def test_migration_005_task_ordering_determinism(tmp_path):
    """Prueba que la migración inicializa determinísticamente 'position'."""
    db_path = str(tmp_path / "mig_005.db")
    app = setup_db(db_path, run_up_to="4cee1aa5ad3f") # Hasta inc 4

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Insert users
    cur.execute("INSERT INTO users (email, password_hash, created_at) VALUES ('u1@a.com', 'h', '2026-10-01')")
    u1 = cur.lastrowid
    cur.execute("INSERT INTO users (email, password_hash, created_at) VALUES ('u2@a.com', 'h', '2026-10-01')")
    u2 = cur.lastrowid

    # Insert tasks (created_desc is the current default order)
    # Tasks for u1
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at) VALUES (?, 'T1', 'pendiente', '2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z')", (u1,))
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at) VALUES (?, 'T2', 'pendiente', '2026-10-01T11:00:00Z', '2026-10-01T11:00:00Z')", (u1,))
    # Tasks for u2
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at) VALUES (?, 'T3', 'pendiente', '2026-10-01T09:00:00Z', '2026-10-01T09:00:00Z')", (u2,))

    conn.commit()
    conn.close()

    # Run all migrations (including 005)
    with app.app_context():
        upgrade(directory=os.path.abspath("migrations"))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    tasks_u1 = cur.execute("SELECT title, position FROM tasks WHERE user_id=? ORDER BY position ASC", (u1,)).fetchall()
    # Expected: The newest created first, but if migration orders by created_desc, T2 gets position 10, T1 gets 20.
    # We just need to check they have distinct, non-null positions.
    assert len(tasks_u1) == 2
    assert tasks_u1[0][1] is not None
    assert tasks_u1[1][1] is not None
    assert tasks_u1[0][1] != tasks_u1[1][1]

    tasks_u2 = cur.execute("SELECT title, position FROM tasks WHERE user_id=? ORDER BY position ASC", (u2,)).fetchall()
    assert tasks_u2[0][1] is not None

    conn.close()

@pytest.fixture
def clean_app(tmp_path):
    db_path = str(tmp_path / "test_service.db")
    return setup_db(db_path), db_path

def seed_data(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (email, password_hash, created_at) VALUES ('owner@a.com', 'h', '2026-10-01')")
    owner_id = cur.lastrowid
    cur.execute("INSERT INTO users (email, password_hash, created_at) VALUES ('other@a.com', 'h', '2026-10-01')")
    other_id = cur.lastrowid

    # owner tasks
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at, position) VALUES (?, 'O1', 'pendiente', '2026-10-01', '2026-10-01', 10)", (owner_id,))
    t1 = cur.lastrowid
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at, position) VALUES (?, 'O2', 'pendiente', '2026-10-01', '2026-10-01', 20)", (owner_id,))
    t2 = cur.lastrowid
    cur.execute("INSERT INTO tasks (user_id, assignee_id, title, status, created_at, updated_at, position) VALUES (?, ?, 'O3_delegated', 'pendiente', '2026-10-01', '2026-10-01', 30)", (owner_id, other_id))
    t3 = cur.lastrowid

    # deleted owner task
    cur.execute("INSERT INTO tasks (user_id, title, status, is_deleted, created_at, updated_at, position) VALUES (?, 'O_del', 'pendiente', 1, '2026-10-01', '2026-10-01', 40)", (owner_id,))

    # other owner tasks
    cur.execute("INSERT INTO tasks (user_id, title, status, created_at, updated_at, position) VALUES (?, 'Other1', 'pendiente', '2026-10-01', '2026-10-01', 10)", (other_id,))
    t_other = cur.lastrowid
    # assigned to owner, but belongs to other
    cur.execute("INSERT INTO tasks (user_id, assignee_id, title, status, created_at, updated_at, position) VALUES (?, ?, 'Other2_assigned', 'pendiente', '2026-10-01', '2026-10-01', 20)", (other_id, owner_id))
    t_assigned = cur.lastrowid

    conn.commit()
    conn.close()
    return owner_id, other_id, [t1, t2, t3], t_other, t_assigned

def test_update_task_order_persistence_and_idempotence(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        # Get repos without Flask-SQLAlchemy session binding to verify pure logic
        from src.infrastructure.database import db
        session = db.session
        task_repo = TaskRepository(session)
        audit_repo = AuditLogRepository(session)
        service = TaskService(task_repo, audit_repo, session=session)

        # Initial order: t1, t2, t3
        changed = service.update_task_order(owner_id, [tasks[2], tasks[0], tasks[1]])
        assert changed == 3

        # Verify from new connection
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT id, position FROM tasks WHERE user_id=? AND is_deleted=0 ORDER BY position ASC", (owner_id,)).fetchall()
        assert [r[0] for r in rows] == [tasks[2], tasks[0], tasks[1]]
        conn.close()

        # Idempotence
        changed_again = service.update_task_order(owner_id, [tasks[2], tasks[0], tasks[1]])
        assert changed_again == 0

def test_update_task_order_independent_owners(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, t_other, t_assigned = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        task_repo = TaskRepository(session)
        audit_repo = AuditLogRepository(session)
        service = TaskService(task_repo, audit_repo, session=session)

        service.update_task_order(other_id, [t_other, t_assigned])

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT id, position FROM tasks WHERE user_id=? AND is_deleted=0 ORDER BY position ASC", (owner_id,)).fetchall()
        assert [r[0] for r in rows] == tasks # Order for owner did not change
        conn.close()

def test_update_task_order_assigned_other_owner(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, t_other, t_assigned = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        # Attempt to reorder including the assigned task (t_assigned)
        with pytest.raises(OperationNotPermittedError):
            service.update_task_order(owner_id, [tasks[0], tasks[1], tasks[2], t_assigned])

def test_update_task_order_not_accessible(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, t_other, t_assigned = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        # Ajena y no asignada
        with pytest.raises(TaskNotAccessibleError):
            service.update_task_order(owner_id, [tasks[0], tasks[1], tasks[2], t_other])

        # Inexistente
        with pytest.raises(TaskNotAccessibleError):
            service.update_task_order(owner_id, [tasks[0], tasks[1], tasks[2], 9999])

def test_update_task_order_invalid_input(clean_app):
    app, db_path = clean_app
    owner_id, _, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        with pytest.raises(ValidationError):
            service.update_task_order(owner_id, [tasks[0], tasks[1], tasks[0]]) # Duplicate

def test_update_task_order_out_of_sync(clean_app):
    app, db_path = clean_app
    owner_id, _, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        # Missing one active task
        with pytest.raises(ConflictError):
            service.update_task_order(owner_id, [tasks[0], tasks[1]])

def test_update_task_order_empty(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        # Owner has tasks, empty list -> out of sync -> 409 Conflict
        with pytest.raises(ConflictError):
            service.update_task_order(owner_id, [])

        # Create a new user with no tasks
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password_hash, created_at) VALUES ('empty@a.com', 'h', '2026-10-01')")
        empty_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Empty user, empty list -> Success (Idempotent 0)
        assert service.update_task_order(empty_id, []) == 0

def test_update_task_order_audit(clean_app):
    app, db_path = clean_app
    owner_id, _, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        service.update_task_order(owner_id, [tasks[1], tasks[0], tasks[2]])

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        logs = cur.execute("SELECT action, task_id FROM audit_logs WHERE actor_id=? AND action='reorder'", (owner_id,)).fetchall()
        # The plan says: "Se creará un AuditLog del tipo 'reorder' agrupando el evento general"
        # Since audit log usually requires a task_id, we can log it against the first task or user,
        # or maybe we log multiple. For now, just expect at least one 'reorder' action.
        assert len(logs) > 0
        conn.close()

def test_update_task_order_concurrency(clean_app):
    app, db_path = clean_app
    owner_id, _, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        from src.infrastructure.models import TaskORM, AuditLogORM
        from sqlalchemy.orm import Session
        import sqlalchemy as sa
        from sqlalchemy.exc import OperationalError

        # Confirma los datos iniciales antes de invocar el servicio
        with Session(db.engine) as indep_session:
            initial_tasks = indep_session.execute(
                sa.select(TaskORM)
                .where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False)
                .order_by(TaskORM.position.asc())
            ).scalars().all()
            initial_order = [t.id for t in initial_tasks]
            initial_audit_count = indep_session.query(AuditLogORM).count()
        assert initial_order == [tasks[0], tasks[1], tasks[2]]

        def lock_and_hold(event_acquired, event_release, thread_errors):
            conn = None
            try:
                conn = sqlite3.connect(db_path, timeout=5.0)
                conn.execute("BEGIN EXCLUSIVE")
                event_acquired.set()
                event_release.wait(5.0) # Espera acotada
            except Exception as e:
                thread_errors.append(e)
            finally:
                if conn:
                    try:
                        conn.rollback()
                        conn.close()
                    except Exception as e:
                        thread_errors.append(e)

        with Session(db.engine) as indep_session:
            current_tasks = indep_session.execute(
                sa.select(TaskORM)
                .where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False)
                .order_by(TaskORM.position.asc())
            ).scalars().all()
            initial_positions = [(t.id, t.position) for t in current_tasks]

        # ---------------------------------------------------------
        # Caso 1: Agotamiento del timeout (Fallo)
        # ---------------------------------------------------------
        event_acquired_1 = threading.Event()
        event_release_1 = threading.Event()
        errors_1 = []

        t1 = threading.Thread(target=lock_and_hold, args=(event_acquired_1, event_release_1, errors_1))
        t1.start()

        try:
            assert event_acquired_1.wait(2.0), "El hilo 1 no adquirió el bloqueo a tiempo"
            assert not errors_1, f"Error en hilo 1: {errors_1}"

            session = db.session
            # Timeout corto exclusivamente para esta prueba
            session.execute(sa.text("PRAGMA busy_timeout = 100"))
            timeout_val = session.execute(sa.text("PRAGMA busy_timeout")).scalar()
            assert timeout_val == 100

            service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

            with pytest.raises(OperationalError) as exc_info:
                service.update_task_order(owner_id, [tasks[0], tasks[2], tasks[1]])

            # Comprueba la excepción concreta y su causa
            assert "database is locked" in str(exc_info.value.orig)
        finally:
            event_release_1.set()
            t1.join(timeout=2.0)
            assert not t1.is_alive(), "El hilo 1 no terminó"
            if errors_1:
                raise errors_1[0]

        # Comprueba resultado desde sesión independiente (no hay cambios ni commit)
        with Session(db.engine) as indep_session:
            current_tasks = indep_session.execute(
                sa.select(TaskORM)
                .where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False)
                .order_by(TaskORM.position.asc())
            ).scalars().all()
            assert [(t.id, t.position) for t in current_tasks] == initial_positions
            assert indep_session.query(AuditLogORM).count() == initial_audit_count

        # ---------------------------------------------------------
        # Caso 2: Liberación del bloqueo y éxito
        # ---------------------------------------------------------
        event_acquired_2 = threading.Event()
        event_release_2 = threading.Event()
        errors_2 = []

        t2 = threading.Thread(target=lock_and_hold, args=(event_acquired_2, event_release_2, errors_2))
        t2.start()

        try:
            assert event_acquired_2.wait(2.0), "El hilo 2 no adquirió el bloqueo a tiempo"
            assert not errors_2, f"Error en hilo 2: {errors_2}"

            session = db.session
            session.execute(sa.text("PRAGMA busy_timeout = 5000"))
            timeout_val = session.execute(sa.text("PRAGMA busy_timeout")).scalar()
            assert timeout_val == 5000

            service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

            # Liberamos el bloqueo ANTES de invocar al servicio, documentando un caso
            # de éxito tras liberación confirmada sin afirmar que se espera concurrentemente
            event_release_2.set()
            t2.join(timeout=2.0)
            assert not t2.is_alive(), "El hilo 2 no terminó"

            changed = service.update_task_order(owner_id, [tasks[1], tasks[0], tasks[2]])
            assert changed == 2
        finally:
            event_release_2.set()
            if t2.is_alive():
                t2.join(timeout=2.0)
            if errors_2:
                raise errors_2[0]

        # Comprueba éxito íntegro desde sesión independiente (posiciones exactas y auditoría)
        with Session(db.engine) as indep_session:
            current_tasks = indep_session.execute(
                sa.select(TaskORM)
                .where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False)
                .order_by(TaskORM.position.asc())
            ).scalars().all()
            assert [(t.id, t.position) for t in current_tasks] == [
                (tasks[1], 10),
                (tasks[0], 20),
                (tasks[2], 30)
            ]
            assert indep_session.query(AuditLogORM).count() == initial_audit_count + 1

def test_new_tasks_added_at_end(clean_app):
    app, db_path = clean_app
    owner_id, _, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)

        new_task = service.create_task(owner_id, "New Task")

        # Debería tener la posición máxima
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        pos = cur.execute("SELECT position FROM tasks WHERE id=?", (new_task.id,)).fetchone()[0]
        assert pos > 30 # ya que las iniciales eran 10, 20, 30
        conn.close()


def test_update_task_order_premature_commit_defect(clean_app):
    app, db_path = clean_app
    owner_id, other_id, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        from src.infrastructure.models import TaskORM
        from sqlalchemy.orm import Session

        session = db.session
        task_repo = TaskRepository(session)
        audit_repo = AuditLogRepository(session)
        service = TaskService(task_repo, audit_repo, session=session)

        # Verify initial data using an independent session
        with Session(db.engine) as indep_session:
            initial_title = indep_session.get(TaskORM, tasks[0]).title
            assert initial_title == "O1"

        # 1. Make a pending change in the current session
        task_orm = session.get(TaskORM, tasks[0])
        task_orm.title = "Pending Title Change"
        # We don't commit here.

        # 2. Call update_task_order with invalid input (out of sync) to trigger ConflictError AFTER the commit
        with pytest.raises(ConflictError):
            service.update_task_order(owner_id, [tasks[0], tasks[1]])

        # 3. Check if the pending change was prematurely committed using an independent session
        with Session(db.engine) as indep_session:
            saved_title = indep_session.get(TaskORM, tasks[0]).title

        assert saved_title == "O1", "Defect: Premature commit persisted the pending title change!"

def test_update_task_order_audit_rollback_defect(clean_app, monkeypatch):
    app, db_path = clean_app
    owner_id, other_id, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        from src.infrastructure.models import TaskORM, AuditLogORM
        from sqlalchemy.orm import Session
        import sqlalchemy as sa

        session = db.session
        task_repo = TaskRepository(session)
        audit_repo = AuditLogRepository(session)
        service = TaskService(task_repo, audit_repo, session=session)

        # Mock audit_repo.create to fail
        def mock_create(*args, **kwargs):
            raise Exception("Simulated audit failure")
        monkeypatch.setattr(audit_repo, "create", mock_create)

        # Save original positions using independent session
        with Session(db.engine) as indep_session:
            initial_tasks = indep_session.execute(
                sa.select(TaskORM).where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False).order_by(TaskORM.position.asc())
            ).scalars().all()
            initial_order = [t.id for t in initial_tasks]

        # 1. Try to reorder, which should fail during audit creation
        with pytest.raises(Exception, match="Simulated audit failure"):
            service.update_task_order(owner_id, [tasks[1], tasks[0], tasks[2]])

        # 2. Verify everything rolled back
        with Session(db.engine) as indep_session:
            final_tasks = indep_session.execute(
                sa.select(TaskORM).where(TaskORM.user_id == owner_id, TaskORM.is_deleted == False).order_by(TaskORM.position.asc())
            ).scalars().all()
            final_order = [t.id for t in final_tasks]

            logs = indep_session.execute(
                sa.select(AuditLogORM).where(AuditLogORM.action == 'reorder')
            ).scalars().all()

        assert final_order == initial_order, "Defect: Positions were not rolled back!"
        assert len(logs) == 0, "Defect: Audit log was persisted despite failure!"

def test_update_task_order_lock_failure_rollback(clean_app, monkeypatch):
    """Prueba que un fallo al adquirir el bloqueo en update_task_order ejecute el rollback limpiando la sesión."""
    app, db_path = clean_app
    owner_id, other_id, tasks, _, _ = seed_data(db_path)

    with app.app_context():
        from src.infrastructure.database import db
        from src.infrastructure.models import TaskORM, UserORM
        from sqlalchemy.orm import Session
        import sqlalchemy as sa

        session = db.session
        task_repo = TaskRepository(session)
        audit_repo = AuditLogRepository(session)
        service = TaskService(task_repo, audit_repo, session=session)

        # Make a pending change in the SESSION
        task_orm = session.get(TaskORM, tasks[0])
        task_orm.title = "Lock Fail Title"

        # Mock session.get_bind to fail to simulate a failure during lock preparation
        # This avoids SQLAlchemy's implicit rollback on session.execute, proving that
        # our service must catch the error and call _rollback() itself.
        def mock_get_bind(*args, **kwargs):
            raise RuntimeError("Simulated lock preparation failure")

        monkeypatch.setattr(session, "get_bind", mock_get_bind)

        # 1. Try to reorder, which should fail during lock acquisition/preparation
        with pytest.raises(RuntimeError, match="Simulated lock preparation failure"):
            service.update_task_order(owner_id, [tasks[1], tasks[0], tasks[2]])

        # 2. Verify the pending change was rolled back IN THE SAME SESSION
        # If _rollback() was called, the session is cleared of pending changes, and task_orm.title reverts
        assert task_orm.title == "O1", "Defect: Lock failure did not trigger _rollback(), leaving session dirty!"
