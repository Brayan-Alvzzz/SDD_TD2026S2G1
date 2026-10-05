import pytest
from unittest.mock import patch
from src.domain.exceptions import ValidationError, UnauthorizedError, ConflictError
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
    other = user_repo.create("other@example.com", "hash")
    third = user_repo.create("third@example.com", "hash")
    db_session.commit()
    task = task_repo.create(owner.id, "Test Task")
    return {"owner": owner, "other": other, "third": third, "task": task}

def test_assign_to_existing_user_keeps_owner(collaboration_service, users_and_task, task_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee_email)
    db_session.commit()

    task = task_repo.get_by_id(task_id)
    assert task.user_id == owner_id
    assert task.assignee_id == users_and_task["other"].id

def test_assign_creates_audit_and_notification(collaboration_service, users_and_task, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    assignee_id = users_and_task["other"].id
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee_email)
    db_session.commit()

    # Verify audit
    audits = audit_repo.get_by_task_id(task_id)
    assign_audits = [a for a in audits if a.action == "assign"]
    assert len(assign_audits) == 1
    assert assign_audits[0].actor_id == owner_id

    # Verify notification
    notifications = notification_repo.list_by_recipient(assignee_id)
    assert len(notifications) == 1
    assert notifications[0].task_id == task_id
    assert notifications[0].actor_id == owner_id

def test_reassign_notifies_only_new_recipient(collaboration_service, users_and_task, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    first_assignee = users_and_task["other"]
    second_assignee = users_and_task["third"]

    collaboration_service.assign_task(task_id, owner_id, first_assignee.email)
    db_session.commit()

    # Reassign
    collaboration_service.assign_task(task_id, owner_id, second_assignee.email)
    db_session.commit()

    audits = audit_repo.get_by_task_id(task_id)
    reassign_audits = [a for a in audits if a.action == "reassign"]
    assert len(reassign_audits) == 1

    first_notifs = notification_repo.list_by_recipient(first_assignee.id)
    assert len(first_notifs) == 1 # Only the first one

    second_notifs = notification_repo.list_by_recipient(second_assignee.id)
    assert len(second_notifs) == 1 # Got the reassign notification

def test_unassign_records_audit_no_notification(collaboration_service, users_and_task, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee = users_and_task["other"]
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee.email)
    db_session.commit()

    # Unassign
    collaboration_service.unassign_task(task_id, owner_id)
    db_session.commit()

    audits = audit_repo.get_by_task_id(task_id)
    unassign_audits = [a for a in audits if a.action == "unassign"]
    assert len(unassign_audits) == 1

    # Should not have created a new notification
    notifs = notification_repo.list_by_recipient(assignee.id)
    assert len(notifs) == 1 # Just the original assign

def test_same_assignee_idempotent(collaboration_service, users_and_task, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee = users_and_task["other"]
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee.email)
    db_session.commit()

    audits_before = len(audit_repo.get_by_task_id(task_id))
    notifs_before = len(notification_repo.list_by_recipient(assignee.id))

    # Reassign to same
    collaboration_service.assign_task(task_id, owner_id, assignee.email)
    db_session.commit()

    audits_after = len(audit_repo.get_by_task_id(task_id))
    notifs_after = len(notification_repo.list_by_recipient(assignee.id))

    assert audits_after == audits_before
    assert notifs_after == notifs_before

def test_reject_self_assignment_and_nonexistent(collaboration_service, users_and_task, db_session):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    owner_email = users_and_task["owner"].email

    with pytest.raises(ValidationError):
        collaboration_service.assign_task(task_id, owner_id, owner_email)

    with pytest.raises(ValidationError):
        collaboration_service.assign_task(task_id, owner_id, "nobody@example.com")

def test_manage_assignments_only_owner(collaboration_service, users_and_task, db_session):
    other_id = users_and_task["other"].id
    third_email = users_and_task["third"].email
    task_id = users_and_task["task"].id

    with pytest.raises(UnauthorizedError):
        collaboration_service.assign_task(task_id, other_id, third_email)

    with pytest.raises(UnauthorizedError):
        collaboration_service.unassign_task(task_id, other_id)

def test_reject_operations_on_deleted_task(collaboration_service, users_and_task, task_repo, db_session):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    assignee_email = users_and_task["other"].email

    task_repo.soft_delete(task_id, owner_id)
    db_session.commit()

    with pytest.raises(Exception): # Usually NotFoundError or UnauthorizedError based on the plan
        collaboration_service.assign_task(task_id, owner_id, assignee_email)

def test_concurrency_protection(collaboration_service, users_and_task, task_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    task_id = users_and_task["task"].id

    # Mock task_repo.set_assignee to simulate 0 rowcount (concurrency)
    with patch.object(task_repo, 'set_assignee', return_value=False):
        with pytest.raises(ConflictError):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)
