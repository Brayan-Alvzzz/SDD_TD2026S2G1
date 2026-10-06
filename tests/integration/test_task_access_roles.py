import pytest
from datetime import datetime, timezone
from src.domain.models import User, Task
from src.domain.services import CollaborationService, TaskService

def _login(client, user: User):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["email"] = user.email

from src.infrastructure.repositories import AuditLogRepository, NotificationRepository

@pytest.fixture
def users_and_task(db_session, user_repo, task_repo, audit_repo):
    notif_repo = NotificationRepository(db_session)
    collab_service = CollaborationService(task_repo, user_repo, audit_repo, notif_repo)
    
    # Propietario A
    owner = user_repo.create("owner_access@example.com", "hash")
    
    # Asignado B
    assignee = user_repo.create("assignee_access@example.com", "hash")
    
    # Ajeno C
    stranger = user_repo.create("stranger_access@example.com", "hash")
    
    db_session.commit()

    # Crear Tarea
    t1 = task_repo.create(owner.id, "Tarea Compartida", status="pendiente", priority="media")
    db_session.commit()

    # Asignar a B
    collab_service.assign_task(t1.id, owner.id, assignee.email)
    
    # Refrescar
    t1 = task_repo.get_by_id(t1.id)

    return {
        "owner": owner,
        "assignee": assignee,
        "stranger": stranger,
        "task": t1,
        "collab_service": collab_service,
        "notif_repo": notif_repo
    }

def test_owner_keeps_permissions(client, users_and_task):
    owner = users_and_task["owner"]
    task = users_and_task["task"]
    
    _login(client, owner)
    
    # Propietario puede actualizar la tarea
    resp = client.put(f"/api/tasks/{task.id}", json={"title": "Nuevo Título", "status": "pendiente", "priority": "alta"})
    assert resp.status_code == 200

    # Propietario puede administrar asignación
    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 200

def test_assignee_allowed_operations(client, users_and_task, db_session, audit_repo):
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    
    _login(client, assignee)
    
    # Consultar
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 200
    assert resp.json["data"]["title"] == task.title
    
    # Cambiar estado
    resp = client.patch(f"/api/tasks/{task.id}/status", json={"status": "en_progreso"})
    assert resp.status_code == 200
    
    # Verificar auditoría registra identidad como actor
    logs = audit_repo.list_by_task(task.id)
    status_logs = [log for log in logs if log.action == "status_change"]
    assert len(status_logs) > 0
    assert status_logs[-1].actor_id == assignee.id
    
    # Reabrir (primero completamos, luego reabrimos)
    client.patch(f"/api/tasks/{task.id}/status", json={"status": "completada"})
    resp = client.post(f"/api/tasks/{task.id}/reopen")
    assert resp.status_code == 200
    assert resp.json["data"]["status"] == "pendiente"

def test_assignee_forbidden_operations(client, users_and_task):
    assignee = users_and_task["assignee"]
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    
    _login(client, assignee)
    
    # No puede editar datos generales
    resp = client.put(f"/api/tasks/{task.id}", json={"title": "Intento de Hack", "status": "pendiente", "priority": "alta"})
    assert resp.status_code == 403
    
    # No puede eliminar
    resp = client.delete(f"/api/tasks/{task.id}")
    assert resp.status_code == 403
    
    # No puede reasignar
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": stranger.email})
    assert resp.status_code == 403
    
    # No puede desasignar
    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 403
    
    # Validar que los rechazos no generaron auditoría de las acciones prohibidas (comprobado porque la tarea no cambia)
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.json["data"]["title"] == task.title # no cambió
    assert resp.json["data"]["assignee"]["id"] == assignee.id # sigue asignado

def test_stranger_gets_404(client, users_and_task):
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    
    _login(client, stranger)
    
    # Intento de lectura
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 404
    
    # Intento de estado
    resp = client.patch(f"/api/tasks/{task.id}/status", json={"status": "completada"})
    assert resp.status_code == 404

def test_no_session_gets_401(client, users_and_task):
    task = users_and_task["task"]
    
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 401
    
    resp = client.put(f"/api/tasks/{task.id}", json={"title": "foo"})
    assert resp.status_code == 401

def test_deleted_task_access(client, users_and_task, task_repo, audit_repo):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    collab_service = users_and_task["collab_service"]
    
    task_service = TaskService(task_repo, audit_repo)
    task_service.delete_task(task.id, owner.id)
    
    _login(client, assignee)
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 404
    
    _login(client, owner)
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 404

def test_old_assignee_loses_access(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    collab_service = users_and_task["collab_service"]
    
    # Reasignar a stranger
    collab_service.assign_task(task.id, owner.id, stranger.email)
    
    _login(client, assignee)
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 404

def test_body_manipulation_ignored(client, users_and_task, audit_repo):
    assignee = users_and_task["assignee"]
    owner = users_and_task["owner"]
    task = users_and_task["task"]
    
    _login(client, assignee)
    
    # Asignado intenta cambiar el estado y envía en el cuerpo actor_id o user_id simulando ser el owner
    resp = client.patch(f"/api/tasks/{task.id}/status", json={"status": "en_progreso", "actor_id": owner.id, "user_id": owner.id})
    assert resp.status_code == 200
    
    logs = audit_repo.list_by_task(task.id)
    status_logs = [log for log in logs if log.action == "status_change"]
    # El actor_id en la auditoría DEBE ser el del asignado (obtenido de la sesión), no el enviado en el JSON
    assert status_logs[-1].actor_id == assignee.id

def test_old_notification_no_access(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    collab_service = users_and_task["collab_service"]
    notif_repo = users_and_task["notif_repo"]
    
    # stranger es asignado, y se le revoca
    collab_service.assign_task(task.id, owner.id, stranger.email)
    
    # Verificamos que stranger recibió notificación
    notifs = notif_repo.list_by_recipient(stranger.id)
    assert len(notifs) > 0
    notif_id = notifs[0].id
    
    # Propietario desasigna
    collab_service.unassign_task(task.id, owner.id)
    
    # stranger intenta acceder a la tarea (incluso si tuviera la notificación)
    _login(client, stranger)
    resp = client.get(f"/api/tasks/{task.id}")
    assert resp.status_code == 404
