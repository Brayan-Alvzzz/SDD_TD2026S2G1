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
