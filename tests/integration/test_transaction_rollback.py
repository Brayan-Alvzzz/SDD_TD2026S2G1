import pytest
from unittest.mock import patch
from src.domain.services import TaskService, UserService


def test_create_task_rolls_back_when_audit_fails(user_service, task_service, task_repo, audit_repo, db_session):
    """Verify that when audit logging fails during task creation, the task creation is rolled back."""
    user = user_service.register_user("rollback_test@example.com", "password123")

    with patch.object(audit_repo, "create", side_effect=RuntimeError("Simulated audit failure")):
        with pytest.raises(RuntimeError, match="Simulated audit failure"):
            task_service.create_task(
                user_id=user.id,
                title="Task that should rollback",
                description="This task should not persist"
            )

    # Verify that no task was persisted
    tasks = task_repo.list_by_user(user.id)
    assert len(tasks) == 0


def test_update_task_status_rolls_back_when_audit_fails(user_service, task_service, task_repo, audit_repo, db_session):
    """Verify that when audit logging fails during status transition, task status modification is rolled back."""
    user = user_service.register_user("rollback_status@example.com", "password123")
    task = task_service.create_task(user_id=user.id, title="Active Task")
    assert task.status == "pendiente"

    with patch.object(audit_repo, "create", side_effect=RuntimeError("Simulated audit transition failure")):
        with pytest.raises(RuntimeError, match="Simulated audit transition failure"):
            task_service.update_task_status(task.id, user.id, "en_progreso")

    # Verify task status in database remains 'pendiente'
    db_session.expire_all()
    persisted_task = task_repo.get_by_id(task.id)
    assert persisted_task.status == "pendiente"

    # Verify audit logs only contain initial 'create' event
    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 1
    assert logs[0].action == "create"


def test_delete_task_rolls_back_when_audit_fails(user_service, task_service, task_repo, audit_repo, db_session):
    """Verify that when audit logging fails during soft delete, task deletion is rolled back and is_deleted remains False."""
    user = user_service.register_user("rollback_del@example.com", "password123")
    task = task_service.create_task(user_id=user.id, title="Task for Delete Rollback")
    assert task.is_deleted is False

    with patch.object(audit_repo, "create", side_effect=RuntimeError("Simulated audit delete failure")):
        with pytest.raises(RuntimeError, match="Simulated audit delete failure"):
            task_service.delete_task(task.id, user.id)

    # Verify task in database remains NOT deleted
    db_session.expire_all()
    persisted = task_repo.get_by_id(task.id)
    assert persisted.is_deleted is False
    assert persisted.deleted_at is None

    # Verify audit logs only contain initial 'create' event (no 'delete')
    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 1
    assert logs[0].action == "create"


def test_reopen_task_rolls_back_when_audit_fails(user_service, task_service, task_repo, audit_repo, db_session):
    """Verify that when audit logging fails during reopen, task status modification is rolled back to 'completada'."""
    user = user_service.register_user("rollback_reopen@example.com", "password123")
    task = task_service.create_task(user_id=user.id, title="Task for Reopen Rollback")
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")

    with patch.object(audit_repo, "create", side_effect=RuntimeError("Simulated audit reopen failure")):
        with pytest.raises(RuntimeError, match="Simulated audit reopen failure"):
            task_service.reopen_task(task.id, user.id)

    # Verify task in database remains 'completada'
    db_session.expire_all()
    persisted = task_repo.get_by_id(task.id)
    assert persisted.status == "completada"

    # Verify audit logs only contain 'create' and 2 'status_change' events (no 'reopen')
    logs = audit_repo.list_by_task(task.id)
    assert len(logs) == 3
    assert all(log.action != "reopen" for log in logs)


