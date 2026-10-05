import pytest
from unittest.mock import patch
from src.domain.services import CollaborationService
from src.infrastructure.repositories import NotificationRepository

@pytest.fixture
def notification_repo(db_session):
    return NotificationRepository(db_session)

@pytest.fixture
def collaboration_service(task_repo, user_repo, audit_repo, notification_repo, db_session):
    return CollaborationService(
        task_repo=task_repo,
        user_repo=user_repo,
        audit_repo=audit_repo,
        notification_repo=notification_repo,
        session=db_session
    )

@pytest.fixture
def users_and_task(user_repo, task_repo, db_session):
    owner = user_repo.create("owner@example.com", "hash")
    assignee = user_repo.create("assignee@example.com", "hash")
    db_session.commit()
    task = task_repo.create(owner.id, "Test Task Rollback")
    return {"owner": owner, "assignee": assignee, "task": task}

def test_rollback_if_audit_fails(collaboration_service, users_and_task, task_repo, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["assignee"].email
    task_id = users_and_task["task"].id

    audits_before = len(audit_repo.get_by_task_id(task_id))
    notifs_before = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))

    with patch.object(audit_repo, 'create', side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)
    
    # Needs to ensure rollback
    # Ensure no partial writes by checking the DB via new clean objects
    db_session.rollback() # Normally the service or route handles this, but since we called the service directly and it bubbled up, we might need to rollback the test session if the service didn't. Wait, the plan says CollaborationService will do session.rollback() on exception. Let's verify by just fetching from DB.
    
    task = task_repo.get_by_id(task_id)
    assert task.assignee_id is None, "Task assignee should not be updated"

    audits_after = len(audit_repo.get_by_task_id(task_id))
    assert audits_after == audits_before, "No audit log should be created"

    notifs_after = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))
    assert notifs_after == notifs_before, "No notification should be created"

def test_rollback_if_notification_fails(collaboration_service, users_and_task, task_repo, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["assignee"].email
    task_id = users_and_task["task"].id

    audits_before = len(audit_repo.get_by_task_id(task_id))
    notifs_before = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))

    with patch.object(notification_repo, 'create', side_effect=Exception("Notif DB Error")):
        with pytest.raises(Exception, match="Notif DB Error"):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)

    db_session.rollback()

    task = task_repo.get_by_id(task_id)
    assert task.assignee_id is None, "Task assignee should not be updated"

    audits_after = len(audit_repo.get_by_task_id(task_id))
    assert audits_after == audits_before, "Audit log should be rolled back"

    notifs_after = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))
    assert notifs_after == notifs_before, "No notification should be created"
