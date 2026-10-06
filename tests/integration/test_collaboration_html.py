import pytest
from bs4 import BeautifulSoup
from src.domain.models import User, Task
from src.infrastructure.repositories import TaskRepository, NotificationRepository, AuditLogRepository
from src.domain.services import CollaborationService
from datetime import datetime, timezone

def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email

@pytest.fixture
def users_and_tasks(app, db_session, user_repo, task_repo):
    owner = user_repo.create("owner_html@example.com", "hash")
    assignee = user_repo.create("assignee_html@example.com", "hash")
    stranger = user_repo.create("stranger_html@example.com", "hash")
    db_session.commit()

    # Crear tareas
    t1 = task_repo.create(owner.id, "Propia no asignada <script>", priority="media", status="pendiente")
    t2 = task_repo.create(owner.id, "Propia asignada", priority="media", status="pendiente")
    t3 = task_repo.create(stranger.id, "Ajena asignada", priority="media", status="pendiente")
    t4 = task_repo.create(owner.id, "Eliminada", priority="media", status="pendiente")
    db_session.commit()

    task_repo.soft_delete(t4.id, owner.id, "2026-10-05T00:00:00Z")
    db_session.commit()

    # Asignaciones
    collab_service = CollaborationService(
        task_repo,
        user_repo,
        AuditLogRepository(db_session),
        NotificationRepository(db_session),
        session=db_session
    )
    collab_service.assign_task(t2.id, owner.id, assignee.email)
    collab_service.assign_task(t3.id, stranger.id, owner.email)

    return {
        "owner": owner,
        "assignee": assignee,
        "stranger": stranger,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "t4": t4,
        "notif_repo": NotificationRepository(db_session)
    }

def test_html_list_includes_roles_and_escaping(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    t1 = users_and_tasks["t1"]
    _login(client, owner)

    resp = client.get("/tasks")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    # Escapado
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

    soup = BeautifulSoup(html, "html.parser")
    
    # Verificamos que el listado incluye las tareas
    # Filtros de rol
    assert soup.find("select", {"name": "role"}) is not None

    # Tarea propia
    row1 = soup.find("tr", {"data-task-id": str(t1.id)})
    assert row1 is not None
    assert row1.get("data-viewer-role") == "owner"
    assert "owner" in row1.text.lower() or "propietario" in row1.text.lower()

    # Tarea ajena asignada a owner (t3)
    t3 = users_and_tasks["t3"]
    row3 = soup.find("tr", {"data-task-id": str(t3.id)})
    assert row3 is not None
    assert row3.get("data-viewer-role") == "assignee"

def test_html_list_controls_only_for_owner(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    t2 = users_and_tasks["t2"] # propia asignada
    t3 = users_and_tasks["t3"] # ajena asignada a mi
    
    _login(client, owner)
    resp = client.get("/tasks")
    soup = BeautifulSoup(resp.data.decode("utf-8"), "html.parser")

    row2 = soup.find("tr", {"data-task-id": str(t2.id)})
    row3 = soup.find("tr", {"data-task-id": str(t3.id)})

    # Botones de editar, eliminar, administrar asignaciones solo en row2
    # Comprobamos enlaces a editar
    edit_btn2 = row2.find("a", href=f"/tasks/{t2.id}/edit")
    assert edit_btn2 is not None

    edit_btn3 = row3.find("a", href=f"/tasks/{t3.id}/edit")
    assert edit_btn3 is None

def test_html_detail_access_and_denials(client, users_and_tasks, db_session, user_repo):
    owner = users_and_tasks["owner"]
    assignee = users_and_tasks["assignee"]
    stranger = users_and_tasks["stranger"]
    t1 = users_and_tasks["t1"]
    t2 = users_and_tasks["t2"] # Tarea de owner asignada a assignee
    t4 = users_and_tasks["t4"] # eliminada

    # Acceso permitido para propietario
    _login(client, owner)
    resp = client.get(f"/tasks/{t1.id}")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.data.decode("utf-8"), "html.parser")
    assert soup.find("form", action=f"/tasks/{t1.id}/delete") is not None

    # Acceso permitido para asignado (solo lectura)
    _login(client, assignee)
    resp = client.get(f"/tasks/{t2.id}")
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.data.decode("utf-8"), "html.parser")
    assert soup.find("form", action=f"/tasks/{t2.id}/delete") is None

    # Rechazo para ajeno
    _login(client, stranger)
    resp = client.get(f"/tasks/{t1.id}")
    assert resp.status_code == 404

    # Rechazo para tarea eliminada
    _login(client, owner)
    resp = client.get(f"/tasks/{t4.id}")
    assert resp.status_code == 404

    # Desasignar
    repo = TaskRepository(db_session)
    collab = CollaborationService(repo, user_repo, AuditLogRepository(db_session), NotificationRepository(db_session), session=db_session)
    collab.unassign_task(t2.id, owner.id)

    # Rechazo para antiguo asignado
    _login(client, assignee)
    resp = client.get(f"/tasks/{t2.id}")
    assert resp.status_code == 404

def test_html_assign_form_validates_backend_auth(client, users_and_tasks):
    assignee = users_and_tasks["assignee"]
    stranger = users_and_tasks["stranger"]
    t2 = users_and_tasks["t2"] # De owner asignada a assignee

    _login(client, assignee)
    # Intento de reasignar
    resp = client.post(f"/tasks/{t2.id}/assignee", data={"assignee_email": stranger.email})
    assert resp.status_code == 403

def test_html_notifications_list_and_nav(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    assignee = users_and_tasks["assignee"]
    
    _login(client, assignee)
    resp = client.get("/notifications")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    
    soup = BeautifulSoup(html, "html.parser")
    # T2 asignada a assignee, debería tener una notif
    assert "Asignada el" in html
    
    # Navegación tiene contador
    nav = soup.find("nav")
    assert nav is not None
    assert "1" in nav.text # 1 no leída

    # Marcar leída
    notifs = users_and_tasks["notif_repo"].list_by_recipient(assignee.id)
    n_id = notifs[0].id
    
    resp_read = client.post(f"/notifications/{n_id}/read")
    assert resp_read.status_code == 302 # redirect back

    resp2 = client.get("/notifications")
    assert "0" in BeautifulSoup(resp2.data.decode("utf-8"), "html.parser").find("nav").text

def test_html_notification_unavailable_state(client, users_and_tasks, db_session, user_repo):
    owner = users_and_tasks["owner"]
    assignee = users_and_tasks["assignee"]
    t2 = users_and_tasks["t2"]

    # Desasignar
    repo = TaskRepository(db_session)
    collab = CollaborationService(repo, user_repo, AuditLogRepository(db_session), NotificationRepository(db_session), session=db_session)
    collab.unassign_task(t2.id, owner.id)

    _login(client, assignee)
    resp = client.get("/notifications")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    assert "ya no disponible" in html.lower()
    assert f"/tasks/{t2.id}" not in html

def test_html_requires_session(client):
    resp = client.get("/tasks/1")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")
    
    resp_notif = client.get("/notifications")
    assert resp_notif.status_code == 302
    assert "/login" in resp_notif.headers.get("Location", "")
