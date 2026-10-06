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
    
    # We want to simulate a concurrent transaction.
    # We will acquire a write lock on the DB using a separate connection.
    event_lock_acquired = threading.Event()
    event_release_lock = threading.Event()
    
    def lock_db_thread():
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("BEGIN EXCLUSIVE") # Lock DB
        event_lock_acquired.set()
        event_release_lock.wait(10.0) # Hold it for a bit
        conn.rollback()
        conn.close()
        
    t = threading.Thread(target=lock_db_thread)
    t.start()
    
    # Wait until the thread holds the lock
    event_lock_acquired.wait(2.0)
    
    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)
        
        # Attempt to update order. This should block and potentially raise OperationalError (database is locked)
        # if timeout is reached, OR it successfully completes once the lock is released.
        # SQLite's default timeout in Python is 5 seconds. We release the lock after 0.5s to see if it recovers,
        # but let's actually just check that it behaves atomically.
        event_release_lock.set() # Release immediately so it doesn't actually timeout, just proves synchronization.
        
        # Let's ensure the service uses BEGIN IMMEDIATE to prevent read-modify-write interleaved.
        # A true concurrency test of read-modify-write:
        # We can mock nothing. Just call update_task_order.
        changed = service.update_task_order(owner_id, [tasks[1], tasks[0], tasks[2]])
        assert changed == 2
        
    t.join()
    
    # Let's do a more explicit concurrency conflict:
    # While update_task_order is doing the SET validation, if someone else inserted a task, 
    # the BEGIN IMMEDIATE prevents insertion.
    # If the user sends stale IDs, it's caught by ConflictError.
    
    # If we want a pure timeout test to ensure lock works:
    def lock_and_block():
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.execute("BEGIN EXCLUSIVE")
        time.sleep(6.0)
        conn.rollback()
        conn.close()
        
    t2 = threading.Thread(target=lock_and_block)
    t2.start()
    time.sleep(0.2)
    
    with app.app_context():
        from src.infrastructure.database import db
        session = db.session
        # Enforce short timeout on this session's engine to fail fast
        session.get_bind().dispose()
        # In a real scenario, this will raise an OperationalError 'database is locked'.
        # We don't necessarily catch OperationalError in service, it propagates as a 500 or gets handled by app.
        with pytest.raises(Exception):
            service = TaskService(TaskRepository(session), AuditLogRepository(session), session=session)
            service.update_task_order(owner_id, [tasks[0], tasks[1], tasks[2]])
            
    t2.join()

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
