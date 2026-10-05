import pytest
import json
from src.domain.exceptions import ValidationError, NotFoundError, UnauthorizedError


def test_create_task_success(task_service, user_service):
    user = user_service.register_user("taskuser@example.com", "password123")
    task = task_service.create_task(
        user_id=user.id,
        title="Mi primera tarea",
        description="Detalle de la tarea",
        due_date="2026-10-15"
    )

    assert task.id is not None
    assert task.user_id == user.id
    assert task.title == "Mi primera tarea"
    assert task.description == "Detalle de la tarea"
    assert task.due_date == "2026-10-15"
    assert task.status == "pendiente"


def test_create_task_empty_title_fails(task_service, user_service):
    user = user_service.register_user("taskuser2@example.com", "password123")
    with pytest.raises(ValidationError, match="título.*obligatorio"):
        task_service.create_task(user.id, "   ")


def test_create_task_title_too_long_fails(task_service, user_service):
    user = user_service.register_user("taskuser3@example.com", "password123")
    long_title = "A" * 151
    with pytest.raises(ValidationError, match="150 caracteres"):
        task_service.create_task(user.id, long_title)


def test_create_task_description_too_long_fails(task_service, user_service):
    user = user_service.register_user("taskuser4@example.com", "password123")
    long_desc = "B" * 1001
    with pytest.raises(ValidationError, match="1,000 caracteres"):
        task_service.create_task(user.id, "Título válido", description=long_desc)


def test_list_tasks_ordered_descending(task_service, user_service):
    user = user_service.register_user("taskuser5@example.com", "password123")
    t1 = task_service.create_task(user.id, "Tarea 1 Antigua")
    t2 = task_service.create_task(user.id, "Tarea 2 Nueva")

    tasks = task_service.list_tasks(user.id)
    assert len(tasks) == 2
    # Newest task appears first (created_at DESC)
    assert tasks[0].id == t2.id
    assert tasks[1].id == t1.id


def test_list_tasks_filter_by_status(task_service, user_service):
    user = user_service.register_user("taskuser6@example.com", "password123")
    t1 = task_service.create_task(user.id, "Tarea Pendiente")
    t2 = task_service.create_task(user.id, "Tarea En Progreso")
    task_service.update_task_status(t2.id, user.id, "en_progreso")

    pending_tasks = task_service.list_tasks(user.id, status="pendiente")
    assert len(pending_tasks) == 1
    assert pending_tasks[0].id == t1.id

    progress_tasks = task_service.list_tasks(user.id, status="en_progreso")
    assert len(progress_tasks) == 1
    assert progress_tasks[0].id == t2.id


def test_audit_log_created_on_task_creation(task_service, user_service, audit_repo):
    user = user_service.register_user("taskuser7@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea Auditada")

    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 1
    assert logs[0].action == "create"
    assert logs[0].actor_id == user.id
    details = json.loads(logs[0].details)
    assert details["title"] == "Tarea Auditada"
    assert details["status"] == "pendiente"


def test_update_task_success(task_service, user_service, audit_repo):
    user = user_service.register_user("taskuser8@example.com", "password123")
    task = task_service.create_task(user.id, "Título Inicial", "Descripción inicial")

    updated = task_service.update_task(
        task_id=task.id,
        user_id=user.id,
        title="Título Modificado",
        description="Descripción modificada",
        due_date="2026-11-01"
    )

    assert updated.title == "Título Modificado"
    assert updated.description == "Descripción modificada"
    assert updated.due_date == "2026-11-01"

    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 2
    assert logs[1].action == "update"
    diff = json.loads(logs[1].details)
    assert diff["title"]["old"] == "Título Inicial"
    assert diff["title"]["new"] == "Título Modificado"


def test_update_task_validation_failures(task_service, user_service):
    user = user_service.register_user("taskuser9@example.com", "password123")
    task = task_service.create_task(user.id, "Título Válido")

    with pytest.raises(ValidationError, match="título.*obligatorio"):
        task_service.update_task(task.id, user.id, "   ")

    with pytest.raises(ValidationError, match="150 caracteres"):
        task_service.update_task(task.id, user.id, "X" * 151)

    with pytest.raises(ValidationError, match="1,000 caracteres"):
        task_service.update_task(task.id, user.id, "Título", description="Y" * 1001)


def test_update_task_unauthorized_user(task_service, user_service):
    user1 = user_service.register_user("owner@example.com", "password123")
    user2 = user_service.register_user("intruder@example.com", "password123")
    task = task_service.create_task(user1.id, "Tarea de Owner")

    with pytest.raises(UnauthorizedError):
        task_service.update_task(task.id, user2.id, "Intento de edición")


def test_soft_delete_task_success(task_service, user_service, audit_repo):
    user = user_service.register_user("del_user1@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea a eliminar", "Descripción")

    deleted_task = task_service.delete_task(task.id, user.id)

    assert deleted_task.is_deleted is True
    assert deleted_task.deleted_at is not None

    # Verify audit log entry
    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 2
    assert logs[1].action == "delete"
    details = json.loads(logs[1].details)
    assert details["title"] == "Tarea a eliminar"


def test_soft_delete_excludes_from_list_tasks(task_service, user_service):
    user = user_service.register_user("del_user2@example.com", "password123")
    t1 = task_service.create_task(user.id, "Tarea Activa")
    t2 = task_service.create_task(user.id, "Tarea Descartada")

    task_service.delete_task(t2.id, user.id)

    active_tasks = task_service.list_tasks(user.id)
    active_ids = [t.id for t in active_tasks]
    assert t1.id in active_ids
    assert t2.id not in active_ids

    # Also test status filtered list
    filtered = task_service.list_tasks(user.id, status="pendiente")
    filtered_ids = [t.id for t in filtered]
    assert t1.id in filtered_ids
    assert t2.id not in filtered_ids


def test_soft_delete_duplicate_attempt_fails(task_service, user_service):
    user = user_service.register_user("del_user3@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea Única")

    task_service.delete_task(task.id, user.id)

    # Subsequent deletion must fail
    with pytest.raises((NotFoundError, ValidationError)):
        task_service.delete_task(task.id, user.id)


def test_soft_delete_unauthorized_alien_task(task_service, user_service):
    user_owner = user_service.register_user("del_owner@example.com", "password123")
    user_other = user_service.register_user("del_other@example.com", "password123")
    task = task_service.create_task(user_owner.id, "Tarea Privada")

    with pytest.raises(UnauthorizedError):
        task_service.delete_task(task.id, user_other.id)


def test_soft_delete_blocks_subsequent_modifications(task_service, user_service):
    user = user_service.register_user("del_user4@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea Inalterable")

    task_service.delete_task(task.id, user.id)

    with pytest.raises((ValidationError, NotFoundError)):
        task_service.update_task(task.id, user.id, "Nuevo Título")

    with pytest.raises((ValidationError, NotFoundError)):
        task_service.update_task_status(task.id, user.id, "en_progreso")


