import os
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT", "1")
import pytest
from flask_migrate import upgrade
from src.infrastructure.database import db
from src.infrastructure.repositories import UserRepository, TaskRepository, AuditLogRepository, CategoryRepository
from src.domain.services import UserService, TaskService, CategoryService
from src.web.app import create_app
from flask.testing import FlaskClient
from bs4 import BeautifulSoup

class CSRFTestClient(FlaskClient):
    def open(self, *args, **kwargs):
        from flask import g
        if "csrf_token" in g:
            g.pop("csrf_token", None)

        method = kwargs.get("method", "GET")
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            has_token = False
            if "headers" in kwargs and "X-CSRFToken" in kwargs.get("headers", {}):
                has_token = True
            elif "json" in kwargs and kwargs.get("json") and "csrf_token" in kwargs["json"]:
                has_token = True
            elif "data" in kwargs and isinstance(kwargs.get("data"), dict) and "csrf_token" in kwargs["data"]:
                has_token = True

            if not has_token:
                res = self.get("/login", follow_redirects=True)
                soup = BeautifulSoup(res.data, "html.parser")
                token_input = soup.find("input", {"name": "csrf_token"})
                token = token_input.get("value") if token_input else ""

                if "json" in kwargs:
                    headers = kwargs.get("headers", {})
                    headers["X-CSRFToken"] = token
                    kwargs["headers"] = headers
                else:
                    data = kwargs.get("data", {})
                    if isinstance(data, dict):
                        data["csrf_token"] = token
                        kwargs["data"] = data
        return super().open(*args, **kwargs)



@pytest.fixture
def test_db_path(tmp_path):
    """Provide an isolated temporary SQLite database path for testing."""
    db_file = str(tmp_path / "test_temp.db")
    yield db_file
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except OSError:
            pass


@pytest.fixture
def app(test_db_path):
    """Test Flask application configured with isolated temporary database initialized via versioned Alembic migrations."""
    migrations_dir = os.path.abspath("migrations")
    abs_path = os.path.abspath(test_db_path)
    uri = f"sqlite:///{abs_path.replace(os.sep, '/')}"

    test_config = {
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "DATABASE_PATH": test_db_path,
        "SQLALCHEMY_DATABASE_URI": uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "ENABLE_CONSOLE_PASSWORD_RESET": True,
        "WTF_CSRF_ENABLED": True,
    }
    flask_app = create_app(test_config)
    flask_app.test_client_class = CSRFTestClient

    with flask_app.app_context():
        # Apply versioned Alembic migrations strictly (no db.create_all())
        upgrade(directory=migrations_dir)
        yield flask_app


@pytest.fixture
def db_session(app):
    """Scoped SQLAlchemy database session for testing."""
    with app.app_context():
        yield db.session
        db.session.rollback()
        db.session.remove()


@pytest.fixture
def db_conn(db_session):
    """Provide underlying DBAPI connection for compatibility if needed."""
    return db_session.connection().connection


@pytest.fixture
def user_repo(db_session):
    return UserRepository(db_session)


@pytest.fixture
def task_repo(db_session):
    return TaskRepository(db_session)


@pytest.fixture
def audit_repo(db_session):
    return AuditLogRepository(db_session)


@pytest.fixture
def user_service(user_repo, db_session):
    from src.infrastructure.notifications import ConsoleNotificationService
    notification_svc = ConsoleNotificationService(enabled=True)
    return UserService(user_repo, notification_service=notification_svc, session=db_session)



@pytest.fixture
def task_service(task_repo, audit_repo, db_session):
    return TaskService(task_repo, audit_repo, session=db_session)


@pytest.fixture
def category_repo(db_session):
    return CategoryRepository(db_session)


@pytest.fixture
def category_service(category_repo, db_session):
    return CategoryService(category_repo, session=db_session)



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
