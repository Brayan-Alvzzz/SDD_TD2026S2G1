import pytest
import time
from datetime import datetime, timezone
from src.domain.models import User
from src.domain.services import CollaborationService, TaskService
from src.infrastructure.repositories import AuditLogRepository, NotificationRepository

def _login(client, user: User):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["email"] = user.email

def _get_new_session(db_session):
    return db_session.session_factory()

@pytest.fixture
def users_and_notifications(db_session, user_repo, task_repo, audit_repo):
    notif_repo = NotificationRepository(db_session)
    collab_service = CollaborationService(task_repo, user_repo, audit_repo, notif_repo, db_session)
    task_service = TaskService(task_repo, audit_repo, None, db_session)
    
    owner = user_repo.create("owner_notif@example.com", "hash")
    assignee = user_repo.create("assignee_notif@example.com", "hash")
    stranger = user_repo.create("stranger_notif@example.com", "hash")
    
    db_session.commit()

    t1 = task_repo.create(owner.id, "Tarea Notif 1", status="pendiente", priority="media")
    t2 = task_repo.create(owner.id, "Tarea Notif 2", status="pendiente", priority="alta")
    db_session.commit()

    # Generamos notificaciones reales usando el servicio
    collab_service.assign_task(t1.id, owner.id, assignee.email)
    time.sleep(0.01) # asegurar orden temporal
    collab_service.assign_task(t2.id, owner.id, assignee.email)
    time.sleep(0.01)
    
    # También damos una tarea a stranger
    t3 = task_repo.create(owner.id, "Tarea Stranger", status="pendiente", priority="media")
    db_session.commit()
    collab_service.assign_task(t3.id, owner.id, stranger.email)
    
    return {
        "owner": owner,
        "assignee": assignee,
        "stranger": stranger,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "collab_service": collab_service,
        "task_service": task_service,
        "notif_repo": notif_repo,
        "db_session": db_session
    }

def test_no_session_gets_401(client, users_and_notifications):
    resp = client.get("/api/notifications")
    assert resp.status_code == 401
    
    resp = client.post("/api/notifications/1/read")
    assert resp.status_code == 401

def test_list_only_authenticated_user_and_sorting(client, users_and_notifications):
    assignee = users_and_notifications["assignee"]
    t1 = users_and_notifications["t1"]
    t2 = users_and_notifications["t2"]
    
    _login(client, assignee)
    
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json["data"]
    
    # Debe haber 2 notificaciones para assignee, ninguna de stranger
    assert len(data) == 2
    # El orden debe ser las no leídas primero (ambas lo son) y luego orden temporal descendente (t2 más reciente que t1)
    assert data[0]["task"]["id"] == t2.id
    assert data[1]["task"]["id"] == t1.id
    assert resp.json["meta"]["unread_count"] == 2
    
def test_mark_as_read_idempotent(client, users_and_notifications):
    assignee = users_and_notifications["assignee"]
    notif_repo = users_and_notifications["notif_repo"]
    db_session = users_and_notifications["db_session"]
    
    notifs = notif_repo.list_by_recipient(assignee.id)
    target_notif = notifs[0]
    
    _login(client, assignee)
    
    # Marcar leída
    resp = client.post(f"/api/notifications/{target_notif.id}/read")
    assert resp.status_code == 200
    
    # Comprobar estado en base de datos desde otra sesión
    session2 = _get_new_session(db_session)
    repo2 = NotificationRepository(session2)
    n2 = repo2._get_orm(target_notif.id)
    assert n2.is_read is True
    first_read_at = n2.read_at
    assert first_read_at is not None
    session2.close()
    
    # Repetir lectura
    time.sleep(0.01)
    resp2 = client.post(f"/api/notifications/{target_notif.id}/read")
    assert resp2.status_code == 200
    
    # Comprobar que no cambia read_at
    session3 = _get_new_session(db_session)
    repo3 = NotificationRepository(session3)
    n3 = repo3._get_orm(target_notif.id)
    assert n3.read_at == first_read_at
    session3.close()

def test_mark_as_read_others_or_nonexistent_returns_404(client, users_and_notifications):
    assignee = users_and_notifications["assignee"]
    stranger = users_and_notifications["stranger"]
    notif_repo = users_and_notifications["notif_repo"]
    db_session = users_and_notifications["db_session"]
    
    stranger_notifs = notif_repo.list_by_recipient(stranger.id)
    stranger_notif_id = stranger_notifs[0].id
    
    _login(client, assignee)
    
    # Intento marcar ajena simulando el cuerpo
    resp = client.post(f"/api/notifications/{stranger_notif_id}/read", json={"recipient_id": stranger.id, "user_id": stranger.id})
    assert resp.status_code == 404
    
    # Inexistente
    resp = client.post("/api/notifications/99999/read")
    assert resp.status_code == 404
    
    # Confirmar sin cambios
    session2 = _get_new_session(db_session)
    repo2 = NotificationRepository(session2)
    n2 = repo2._get_orm(stranger_notif_id)
    assert n2.is_read is False
    session2.close()

def test_read_notifications_stay_in_history_and_sorting(client, users_and_notifications):
    assignee = users_and_notifications["assignee"]
    notif_repo = users_and_notifications["notif_repo"]
    
    notifs = notif_repo.list_by_recipient(assignee.id)
    notif_t2 = [n for n in notifs if n.task_id == users_and_notifications["t2"].id][0]
    
    _login(client, assignee)
    
    # Marcar t2 leída
    client.post(f"/api/notifications/{notif_t2.id}/read")
    
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json["data"]
    
    assert resp.json["meta"]["unread_count"] == 1
    assert len(data) == 2
    
    # t1 (no leída) debe estar primero, t2 (leída) debe estar después
    assert data[0]["task"]["id"] == users_and_notifications["t1"].id
    assert data[0]["is_read"] is False
    assert data[1]["task"]["id"] == users_and_notifications["t2"].id
    assert data[1]["is_read"] is True

def test_available_status_derived_correctly(client, users_and_notifications):
    owner = users_and_notifications["owner"]
    assignee = users_and_notifications["assignee"]
    t1 = users_and_notifications["t1"]
    collab_service = users_and_notifications["collab_service"]
    
    _login(client, assignee)
    
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data_t1 = [n for n in resp.json["data"] if n.get("task") and n["task"]["id"] == t1.id][0]
    assert data_t1["available"] is True
    assert data_t1["message"].startswith("Asignada el ")
    assert data_t1["message"].endswith(f" por {owner.email}")
    assert "Tarea Notif 1" not in data_t1["message"]
    
    # Desasignar t1
    collab_service.unassign_task(t1.id, owner.id)
    
    # Verificar
    resp2 = client.get("/api/notifications")
    data_t1_after = [n for n in resp2.json["data"] if n["id"] == data_t1["id"]][0]
    assert data_t1_after["available"] is False
    assert data_t1_after.get("task") is None
    assert data_t1_after["message"] == data_t1["message"]
    
    # Volver a asignar a B
    collab_service.assign_task(t1.id, owner.id, assignee.email)
    
    resp3 = client.get("/api/notifications")
    data = resp3.json["data"]
    assert len(data) == 3
    
    new_t1_notif = [n for n in data if n["available"] is True and n.get("task") and n["task"]["id"] == t1.id][0]
    old_t1_notif = [n for n in data if n["id"] == data_t1["id"]][0]
    
    assert old_t1_notif["available"] is False
    assert old_t1_notif.get("task") is None
    assert new_t1_notif["available"] is True

def test_task_deletion_makes_notification_unavailable(client, users_and_notifications):
    owner = users_and_notifications["owner"]
    stranger = users_and_notifications["stranger"]
    t3 = users_and_notifications["t3"]
    task_service = users_and_notifications["task_service"]
    
    task_service.delete_task(t3.id, owner.id)
    
    _login(client, stranger)
    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    data = resp.json["data"]
    
    assert len(data) == 1
    assert data[0]["available"] is False
    assert data[0].get("task") is None
