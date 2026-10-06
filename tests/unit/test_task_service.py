import pytest
import json
from datetime import datetime, timedelta, timezone
from src.domain.exceptions import ValidationError, NotFoundError, UnauthorizedError, InvalidStateTransitionError, TaskNotAccessibleError


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

    with pytest.raises((ValidationError, NotFoundError, TaskNotAccessibleError)):
        task_service.update_task(task.id, user.id, "Nuevo Título")

    with pytest.raises((ValidationError, NotFoundError, TaskNotAccessibleError)):
        task_service.update_task_status(task.id, user.id, "en_progreso")


def test_reopen_task_success(task_service, user_service, audit_repo):
    user = user_service.register_user("reopen_user1@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea a completar y reabrir")
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")

    reopened = task_service.reopen_task(task.id, user.id)
    assert reopened.status == "pendiente"

    # Verify audit log entry
    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 4
    reopen_log = logs[-1]
    assert reopen_log.action == "reopen"
    details = json.loads(reopen_log.details)
    assert details["from"] == "completada"
    assert details["to"] == "pendiente"


def test_reopen_task_non_completed_fails(task_service, user_service):
    user = user_service.register_user("reopen_user2@example.com", "password123")
    t_pending = task_service.create_task(user.id, "Tarea Pendiente")
    t_progress = task_service.create_task(user.id, "Tarea En Progreso")
    task_service.update_task_status(t_progress.id, user.id, "en_progreso")

    # Reopening pending task must fail
    with pytest.raises(InvalidStateTransitionError):
        task_service.reopen_task(t_pending.id, user.id)

    # Reopening in_progress task must fail
    with pytest.raises(InvalidStateTransitionError):
        task_service.reopen_task(t_progress.id, user.id)


def test_reopen_task_deleted_fails(task_service, user_service):
    user = user_service.register_user("reopen_user3@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea Completada y luego Borrada")
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")
    task_service.delete_task(task.id, user.id)

    # Reopening deleted task must fail
    with pytest.raises((NotFoundError, ValidationError)):
        task_service.reopen_task(task.id, user.id)


def test_reopen_task_unauthorized_alien(task_service, user_service):
    user_owner = user_service.register_user("reopen_owner@example.com", "password123")
    user_alien = user_service.register_user("reopen_alien@example.com", "password123")
    task = task_service.create_task(user_owner.id, "Tarea Completada de Owner")
    task_service.update_task_status(task.id, user_owner.id, "en_progreso")
    task_service.update_task_status(task.id, user_owner.id, "completada")

    with pytest.raises(UnauthorizedError):
        task_service.reopen_task(task.id, user_alien.id)


def test_reopen_task_nonexistent_fails(task_service, user_service):
    user = user_service.register_user("reopen_user4@example.com", "password123")
    with pytest.raises(NotFoundError):
        task_service.reopen_task(99999, user.id)


# ============================================================================
# HU-07: Prioridad de Tareas y Ordenamiento (Unit Tests)
# ============================================================================

def test_create_task_assigns_default_media_priority(task_service, user_service):
    """Creating a task without specifying priority must assign 'media' by default."""
    user = user_service.register_user("prio_user1@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea sin prioridad explícita")
    assert task.priority == "media"


def test_create_task_with_explicit_priority(task_service, user_service):
    """Creating a task with an explicit valid priority ('alta', 'media', 'baja') must store it correctly."""
    user = user_service.register_user("prio_user2@example.com", "password123")
    t_alta = task_service.create_task(user.id, "Tarea Alta", priority="alta")
    t_media = task_service.create_task(user.id, "Tarea Media", priority="media")
    t_baja = task_service.create_task(user.id, "Tarea Baja", priority="baja")

    assert t_alta.priority == "alta"
    assert t_media.priority == "media"
    assert t_baja.priority == "baja"


def test_create_task_invalid_priority_raises_validation_error(task_service, user_service):
    """Attempting to create a task with an invalid priority must raise ValidationError."""
    user = user_service.register_user("prio_user3@example.com", "password123")
    with pytest.raises(ValidationError, match="prioridad"):
        task_service.create_task(user.id, "Tarea Inválida", priority="urgente")

    with pytest.raises(ValidationError, match="prioridad"):
        task_service.create_task(user.id, "Tarea Inválida 2", priority="ninguna")


def test_update_task_priority_success_and_audit_log(task_service, user_service, audit_repo):
    """Updating task priority succeeds, changes state, and records priority_change in audit log."""
    user = user_service.register_user("prio_user4@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea para cambiar prioridad", priority="media")
    assert task.priority == "media"

    updated = task_service.update_task_priority(task.id, user.id, "alta")
    assert updated.priority == "alta"

    # Verify audit log
    logs = audit_repo.list_by_task(task.id)
    prio_logs = [log for log in logs if log.action == "priority_change"]
    assert len(prio_logs) == 1
    prio_log = prio_logs[0]
    assert prio_log.actor_id == user.id
    details = json.loads(prio_log.details)
    assert details["old_priority"] == "media"
    assert details["new_priority"] == "alta"


def test_update_task_priority_invalid_value_fails(task_service, user_service):
    """Updating priority to an unallowed value raises ValidationError."""
    user = user_service.register_user("prio_user5@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea de prueba")

    with pytest.raises(ValidationError, match="prioridad"):
        task_service.update_task_priority(task.id, user.id, "critica")


def test_update_task_priority_unauthorized_user_fails(task_service, user_service):
    """A user cannot update the priority of another user's task."""
    user_owner = user_service.register_user("prio_owner@example.com", "password123")
    user_alien = user_service.register_user("prio_alien@example.com", "password123")
    task = task_service.create_task(user_owner.id, "Tarea de Owner")

    with pytest.raises(UnauthorizedError):
        task_service.update_task_priority(task.id, user_alien.id, "alta")


def test_update_task_priority_deleted_task_fails(task_service, user_service):
    """Attempting to update priority of a deleted task raises NotFoundError or ValidationError."""
    user = user_service.register_user("prio_user6@example.com", "password123")
    task = task_service.create_task(user.id, "Tarea a borrar")
    task_service.delete_task(task.id, user.id)

    with pytest.raises((NotFoundError, ValidationError, TaskNotAccessibleError)):
        task_service.update_task_priority(task.id, user.id, "alta")


def test_list_tasks_default_order_is_created_descending(task_service, user_service):
    """When sort is omitted or 'created_desc', list_tasks returns created_at DESC order."""
    user = user_service.register_user("prio_user7@example.com", "password123")
    t1 = task_service.create_task(user.id, "Tarea 1 (Baja)", priority="baja")
    t2 = task_service.create_task(user.id, "Tarea 2 (Alta)", priority="alta")
    t3 = task_service.create_task(user.id, "Tarea 3 (Media)", priority="media")

    tasks_default = task_service.list_tasks(user.id)
    assert [t.id for t in tasks_default] == [t3.id, t2.id, t1.id]

    tasks_explicit = task_service.list_tasks(user.id, sort="created_desc")
    assert [t.id for t in tasks_explicit] == [t3.id, t2.id, t1.id]


def test_list_tasks_sort_by_priority_desc(task_service, user_service):
    """When sort='priority_desc', tasks return in strict hierarchy: alta -> media -> baja."""
    user = user_service.register_user("prio_user8@example.com", "password123")
    t_baja = task_service.create_task(user.id, "Tarea Baja", priority="baja")
    t_media = task_service.create_task(user.id, "Tarea Media", priority="media")
    t_alta = task_service.create_task(user.id, "Tarea Alta", priority="alta")

    tasks = task_service.list_tasks(user.id, sort="priority_desc")
    priorities = [t.priority for t in tasks]
    assert priorities == ["alta", "media", "baja"]
    assert tasks[0].id == t_alta.id
    assert tasks[1].id == t_media.id
    assert tasks[2].id == t_baja.id


def test_list_tasks_sort_by_priority_asc(task_service, user_service):
    """When sort='priority_asc', tasks return in reverse hierarchy: baja -> media -> alta."""
    user = user_service.register_user("prio_user9@example.com", "password123")
    t_baja = task_service.create_task(user.id, "Tarea Baja", priority="baja")
    t_media = task_service.create_task(user.id, "Tarea Media", priority="media")
    t_alta = task_service.create_task(user.id, "Tarea Alta", priority="alta")

    tasks = task_service.list_tasks(user.id, sort="priority_asc")
    priorities = [t.priority for t in tasks]
    assert priorities == ["baja", "media", "alta"]


def test_list_tasks_sort_by_priority_tie_breaking(task_service, user_service):
    """Tasks with the same priority tie-break by created_at DESC (newest first)."""
    user = user_service.register_user("prio_user10@example.com", "password123")
    t_alta_old = task_service.create_task(user.id, "Alta Antigua", priority="alta")
    t_alta_new = task_service.create_task(user.id, "Alta Nueva", priority="alta")
    t_media = task_service.create_task(user.id, "Media", priority="media")

    tasks = task_service.list_tasks(user.id, sort="priority_desc")
    assert [t.id for t in tasks] == [t_alta_new.id, t_alta_old.id, t_media.id]


# ============================================================================
# HU-08: Categorías de Tareas sin Eliminación en Cascada (Unit Tests)
# ============================================================================

def test_create_task_with_valid_category(task_service, user_service, category_service):
    """Creating a task with a valid owned category sets category_id and resolves category_name."""
    user = user_service.register_user("task_cat_user1@example.com", "password123")
    cat = category_service.create_category(user.id, "Frontend")

    task = task_service.create_task(user.id, "Maquetar UI", category_id=cat.id)
    assert task.category_id == cat.id
    assert task.category_name == "Frontend"


def test_create_task_with_alien_category_rejected(task_service, user_service, category_service):
    """Creating a task with a category belonging to another user must be rejected."""
    user_owner = user_service.register_user("cat_owner2@example.com", "password123")
    user_alien = user_service.register_user("cat_alien2@example.com", "password123")
    cat_owner = category_service.create_category(user_owner.id, "OwnerCat")

    with pytest.raises((ValidationError, UnauthorizedError, NotFoundError)):
        task_service.create_task(user_alien.id, "Tarea Maliciosa", category_id=cat_owner.id)


def test_create_task_with_nonexistent_category_rejected(task_service, user_service):
    """Creating a task with a non-existent category_id must raise ValidationError or NotFoundError."""
    user = user_service.register_user("task_cat_user3@example.com", "password123")
    with pytest.raises((ValidationError, NotFoundError)):
        task_service.create_task(user.id, "Tarea Fantasma", category_id=99999)


def test_update_task_category_success_and_audit(task_service, user_service, category_service, audit_repo):
    """Updating a task's category records action='category_change' in persistent audit logs."""
    user = user_service.register_user("task_cat_user4@example.com", "password123")
    cat1 = category_service.create_category(user.id, "Sprint 1")
    cat2 = category_service.create_category(user.id, "Sprint 2")

    task = task_service.create_task(user.id, "Feature X", category_id=cat1.id)
    assert task.category_id == cat1.id

    updated = task_service.update_task_category(task.id, user.id, cat2.id)
    assert updated.category_id == cat2.id

    logs = audit_repo.list_by_task(task.id)
    cat_logs = [log for log in logs if log.action == "category_change"]
    assert len(cat_logs) == 1
    assert str(cat1.id) in cat_logs[0].details or cat1.id == cat_logs[0].details
    assert str(cat2.id) in cat_logs[0].details or cat2.id == cat_logs[0].details


def test_unlink_task_category_with_none_and_audit(task_service, user_service, category_service, audit_repo):
    """Setting category_id=None unlinks the task and records action='category_change'."""
    user = user_service.register_user("task_cat_user5@example.com", "password123")
    cat = category_service.create_category(user.id, "Temporal")

    task = task_service.create_task(user.id, "Tarea con Cat", category_id=cat.id)
    assert task.category_id == cat.id

    unlinked = task_service.update_task_category(task.id, user.id, None)
    assert unlinked.category_id is None

    logs = audit_repo.list_by_task(task.id)
    cat_logs = [log for log in logs if log.action == "category_change"]
    assert len(cat_logs) == 1


def test_update_task_category_alien_or_unauthorized(task_service, user_service, category_service):
    """Assigning another user's category or updating another user's task category is rejected."""
    user_a = user_service.register_user("task_cat_user6a@example.com", "password123")
    user_b = user_service.register_user("task_cat_user6b@example.com", "password123")

    cat_b = category_service.create_category(user_b.id, "Cat de B")
    task_a = task_service.create_task(user_a.id, "Tarea de A")

    # User A tries to assign User B's category to User A's task
    with pytest.raises((ValidationError, UnauthorizedError, NotFoundError)):
        task_service.update_task_category(task_a.id, user_a.id, cat_b.id)

    # User B tries to update User A's task
    with pytest.raises((UnauthorizedError, NotFoundError)):
        task_service.update_task_category(task_a.id, user_b.id, cat_b.id)


def test_list_tasks_filter_by_category_id_and_none(task_service, user_service, category_service):
    """list_tasks supports filtering by specific category_id, 'none' (uncategorized), or all."""
    user = user_service.register_user("task_cat_user7@example.com", "password123")
    cat_dev = category_service.create_category(user.id, "Desarrollo")
    cat_qa = category_service.create_category(user.id, "QA")

    t_dev1 = task_service.create_task(user.id, "Dev 1", category_id=cat_dev.id)
    t_dev2 = task_service.create_task(user.id, "Dev 2", category_id=cat_dev.id)
    t_qa1 = task_service.create_task(user.id, "QA 1", category_id=cat_qa.id)
    t_nocat = task_service.create_task(user.id, "Sin Categoria")

    # Filter by specific category
    dev_tasks = task_service.list_tasks(user.id, category_id=cat_dev.id)
    assert len(dev_tasks) == 2
    assert {t.id for t in dev_tasks} == {t_dev1.id, t_dev2.id}

    # Filter by uncategorized ('none')
    none_tasks = task_service.list_tasks(user.id, category_id="none")
    assert len(none_tasks) == 1
    assert none_tasks[0].id == t_nocat.id

    # No filter (all active tasks)
    all_tasks = task_service.list_tasks(user.id)
    assert len(all_tasks) == 4


# ==============================================================================
# Phase 5: Indicación de Tareas Vencidas (HU-09) - T026 Unit Tests
# ==============================================================================

def test_overdue_yesterday_is_true(task_service, user_service):
    """Task with due_date in the past (yesterday UTC) evaluates to is_overdue=True."""
    user = user_service.register_user("overdue_user1@example.com", "password123")
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea de Ayer", due_date=yesterday_utc)
    assert task.is_overdue is True

    fetched = task_service.get_task(task.id, user.id)
    assert fetched.is_overdue is True

    # When in progress, it remains overdue
    task_service.update_task_status(task.id, user.id, "en_progreso")
    in_prog = task_service.get_task(task.id, user.id)
    assert in_prog.is_overdue is True


def test_overdue_today_is_false(task_service, user_service):
    """Task with due_date equal to today UTC is NOT overdue (due date is full day)."""
    user = user_service.register_user("overdue_user2@example.com", "password123")
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea de Hoy", due_date=today_utc)
    assert task.is_overdue is False

    fetched = task_service.get_task(task.id, user.id)
    assert fetched.is_overdue is False


def test_overdue_tomorrow_is_false(task_service, user_service):
    """Task with future due_date is NOT overdue."""
    user = user_service.register_user("overdue_user3@example.com", "password123")
    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea Futura", due_date=tomorrow_utc)
    assert task.is_overdue is False

    fetched = task_service.get_task(task.id, user.id)
    assert fetched.is_overdue is False


def test_overdue_completed_task_with_past_due_date_is_false(task_service, user_service):
    """Completed tasks are NEVER overdue even if their due_date is in the past."""
    user = user_service.register_user("overdue_user4@example.com", "password123")
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea Completada de Ayer", due_date=yesterday_utc)
    assert task.is_overdue is True

    task_service.update_task_status(task.id, user.id, "en_progreso")
    completed = task_service.update_task_status(task.id, user.id, "completada")
    assert completed.status == "completada"
    assert completed.is_overdue is False

    fetched = task_service.get_task(task.id, user.id)
    assert fetched.is_overdue is False

    completed_list = task_service.list_tasks(user.id, status="completada")
    assert len(completed_list) == 1
    assert completed_list[0].is_overdue is False


def test_overdue_soft_deleted_task_is_false(task_service, user_service):
    """Soft-deleted tasks are NEVER overdue."""
    user = user_service.register_user("overdue_user5@example.com", "password123")
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea Borrada de Ayer", due_date=yesterday_utc)
    assert task.is_overdue is True

    deleted = task_service.delete_task(task.id, user.id)
    assert deleted.is_overdue is False

    fetched_deleted = task_service.get_task(task.id, user.id, include_deleted=True)
    assert fetched_deleted.is_overdue is False


def test_overdue_null_or_empty_due_date_is_false(task_service, user_service):
    """Tasks without a due_date are NEVER overdue."""
    user = user_service.register_user("overdue_user6@example.com", "password123")

    task_none = task_service.create_task(user.id, "Tarea Sin Fecha")
    assert task_none.is_overdue is False

    fetched = task_service.get_task(task_none.id, user.id)
    assert fetched.is_overdue is False


def test_overdue_reopened_past_due_task_becomes_overdue(task_service, user_service):
    """Reopening a completed task whose due_date is in the past immediately restores is_overdue=True."""
    user = user_service.register_user("overdue_user7@example.com", "password123")
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    task = task_service.create_task(user.id, "Tarea a Reabrir", due_date=yesterday_utc)
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")

    completed = task_service.get_task(task.id, user.id)
    assert completed.is_overdue is False

    # Reopen
    reopened = task_service.reopen_task(task.id, user.id)
    assert reopened.status == "pendiente"
    assert reopened.is_overdue is True

    fetched = task_service.get_task(task.id, user.id)
    assert fetched.is_overdue is True


def test_overdue_update_due_date_toggles_flag(task_service, user_service):
    """Updating a task's due_date between future and past dynamically updates is_overdue."""
    user = user_service.register_user("overdue_user8@example.com", "password123")
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Start in the future
    task = task_service.create_task(user.id, "Tarea Dinamica", due_date=tomorrow_utc)
    assert task.is_overdue is False

    # Update to yesterday -> becomes overdue
    updated_past = task_service.update_task(task.id, user.id, title="Tarea Dinamica", due_date=yesterday_utc)
    assert updated_past.is_overdue is True

    # Update back to tomorrow -> no longer overdue
    updated_future = task_service.update_task(task.id, user.id, title="Tarea Dinamica", due_date=tomorrow_utc)
    assert updated_future.is_overdue is False






