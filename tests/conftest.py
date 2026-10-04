import os
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT", "1")
import pytest
import sqlite3
from src.infrastructure.database import init_db_schema
from src.infrastructure.repositories import UserRepository, TaskRepository, AuditLogRepository
from src.domain.services import UserService, TaskService
from src.web.app import create_app


@pytest.fixture
def db_conn():
    """In-memory SQLite database fixture with foreign keys enabled."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def user_repo(db_conn):
    return UserRepository(db_conn)


@pytest.fixture
def task_repo(db_conn):
    return TaskRepository(db_conn)


@pytest.fixture
def audit_repo(db_conn):
    return AuditLogRepository(db_conn)


@pytest.fixture
def user_service(user_repo):
    return UserService(user_repo)


@pytest.fixture
def task_service(task_repo, audit_repo):
    return TaskService(task_repo, audit_repo)


@pytest.fixture
def app(db_conn):
    """Test Flask application configured with in-memory database."""
    test_config = {
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "DATABASE_CONN": db_conn
    }
    app = create_app(test_config)
    return app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client, user_service):
    """Test client with a pre-registered and logged in user."""
    user = user_service.register_user("testuser@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email
    return client, user
