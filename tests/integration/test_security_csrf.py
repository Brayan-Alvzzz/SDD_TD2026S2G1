import pytest
from bs4 import BeautifulSoup
from src.infrastructure.database import db
from src.infrastructure.models import TaskORM, AuditLogORM

def get_csrf_token(client):
    """Extrae el token CSRF de la cabecera usando una ruta GET segura (por ejemplo, /tasks)."""
    response = client.get("/tasks")
    soup = BeautifulSoup(response.data, "html.parser")
    meta = soup.find("meta", {"name": "csrf-token"})
    if meta:
        return meta.get("content")

    # Intenta buscar en un form si aún no hay meta tag
    token_input = soup.find("input", {"name": "csrf_token"})
    if token_input:
        return token_input.get("value")
    return ""


def test_csrf_missing_token_rejected_post(auth_client, app):
    client, user = auth_client

    with app.app_context():
        initial_task_count = db.session.query(TaskORM).count()
        initial_audit_count = db.session.query(AuditLogORM).count()

    from flask.testing import FlaskClient
    app.test_client_class = FlaskClient
    raw_client = app.test_client()
    with client.session_transaction() as sess:
        with raw_client.session_transaction() as raw_sess:
            for k, v in sess.items():
                raw_sess[k] = v

    response = raw_client.post("/tasks", data={
        "title": "CSRF Attack Task",
        "description": "No token"
    })

    assert response.status_code == 400
    assert b"CSRF" in response.data or b"The CSRF token is missing" in response.data

    with app.app_context():
        assert db.session.query(TaskORM).count() == initial_task_count
        assert db.session.query(AuditLogORM).count() == initial_audit_count


def test_csrf_invalid_token_rejected_put(auth_client, task_service, app):
    client, user = auth_client

    with app.app_context():
        task = task_service.create_task(user.id, "Original Task", "")
        task_id = task.id
        initial_audit_count = db.session.query(AuditLogORM).count()

    # Intento PUT vía API
    response = client.put(f"/api/tasks/{task_id}", json={
        "title": "Hacked Title"
    }, headers={"X-CSRFToken": "invalid-token-123"})

    assert response.status_code == 400

    with app.app_context():
        task_db = db.session.get(TaskORM, task_id)
        assert task_db.title == "Original Task"
        assert db.session.query(AuditLogORM).count() == initial_audit_count


def test_csrf_other_session_token_rejected_patch(client, user_service, task_service, app):
    user1 = user_service.register_user("user1@example.com", "password123")
    user2 = user_service.register_user("user2@example.com", "password123")

    with app.app_context():
        task = task_service.create_task(user1.id, "User 1 Task", "")
        task_id = task.id

    # Inicia sesión como user2 y obtiene SU token CSRF
    with client.session_transaction() as sess:
        sess["user_id"] = user2.id
        sess["user_email"] = user2.email

    token_user2 = get_csrf_token(client)

    # Inicia sesión como user1
    with client.session_transaction() as sess:
        sess.clear()
        sess["user_id"] = user1.id
        sess["user_email"] = user1.email

    # User 1 intenta modificar la tarea pero con el token capturado de User 2
    response = client.patch(f"/api/tasks/{task_id}/status", json={
        "status": "en_progreso"
    }, headers={"X-CSRFToken": token_user2})

    assert response.status_code == 400

    with app.app_context():
        task_db = db.session.get(TaskORM, task_id)
        assert task_db.status == "pendiente"


def test_csrf_missing_token_rejected_delete(auth_client, task_service, app):
    client, user = auth_client
    with app.app_context():
        task = task_service.create_task(user.id, "To Delete", "")
        task_id = task.id

    from flask.testing import FlaskClient
    app.test_client_class = FlaskClient
    raw_client = app.test_client()
    with client.session_transaction() as sess:
        with raw_client.session_transaction() as raw_sess:
            for k, v in sess.items():
                raw_sess[k] = v
    response = raw_client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 400

    with app.app_context():
        task_db = db.session.get(TaskORM, task_id)
        assert task_db.is_deleted is False


def test_csrf_valid_token_accepted(auth_client, task_service, app):
    client, user = auth_client
    token = get_csrf_token(client)

    with app.app_context():
        task = task_service.create_task(user.id, "Valid Task", "")
        task_id = task.id

    response = client.patch(f"/api/tasks/{task_id}/status", json={
        "status": "en_progreso"
    }, headers={"X-CSRFToken": token})

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    with app.app_context():
        task_db = db.session.get(TaskORM, task_id)
        assert task_db.status == "en_progreso"
