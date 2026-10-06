import pytest
from unittest.mock import patch
from src.domain.exceptions import ValidationError, UnauthorizedError, ConflictError, TaskNotAccessibleError
from src.domain.services import CollaborationService
from src.infrastructure.repositories import NotificationRepository
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database import db
from src.infrastructure.models import TaskORM, AuditLogORM, NotificationORM
import sqlalchemy as sa

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
    task = task_repo.create(owner.id, "Test Task")
    db_session.commit()
    return {"owner": owner, "other": other, "third": third, "task": task}

def _get_new_session():
    Session = sessionmaker(bind=db.engine)
    return Session()

def test_assign_to_existing_user_keeps_owner(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee_email)

    with _get_new_session() as verify_session:
        task = verify_session.get(TaskORM, task_id)
        assert task.user_id == owner_id
        assert task.assignee_id == users_and_task["other"].id

def test_assign_creates_audit_and_notification(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    assignee_id = users_and_task["other"].id
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee_email)

    with _get_new_session() as verify_session:
        audits = verify_session.execute(sa.select(AuditLogORM).where(AuditLogORM.task_id == task_id)).scalars().all()
        assign_audits = [a for a in audits if a.action == "assign"]
        assert len(assign_audits) == 1
        assert assign_audits[0].actor_id == owner_id

        notifications = verify_session.execute(sa.select(NotificationORM).where(NotificationORM.recipient_id == assignee_id)).scalars().all()
        assert len(notifications) == 1
        assert notifications[0].task_id == task_id
        assert notifications[0].actor_id == owner_id

def test_notification_message_format(collaboration_service, users_and_task):
    owner = users_and_task["owner"]
    assignee_email = users_and_task["other"].email
    assignee_id = users_and_task["other"].id
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner.id, assignee_email)

    with _get_new_session() as verify_session:
        notifications = verify_session.execute(sa.select(NotificationORM).where(NotificationORM.recipient_id == assignee_id)).scalars().all()
        assert len(notifications) == 1
        msg = notifications[0].message
        assert len(msg) <= 255
        assert owner.email in msg
        assert users_and_task["task"].title not in msg

def test_reassign_notifies_only_new_recipient(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    first_assignee = users_and_task["other"]
    second_assignee = users_and_task["third"]

    collaboration_service.assign_task(task_id, owner_id, first_assignee.email)

    # Reassign
    collaboration_service.assign_task(task_id, owner_id, second_assignee.email)

    with _get_new_session() as verify_session:
        audits = verify_session.execute(sa.select(AuditLogORM).where(AuditLogORM.task_id == task_id)).scalars().all()
        reassign_audits = [a for a in audits if a.action == "reassign"]
        assert len(reassign_audits) == 1

        first_notifs = verify_session.execute(sa.select(NotificationORM).where(NotificationORM.recipient_id == first_assignee.id)).scalars().all()
        assert len(first_notifs) == 1 # Only the first one

        second_notifs = verify_session.execute(sa.select(NotificationORM).where(NotificationORM.recipient_id == second_assignee.id)).scalars().all()
        assert len(second_notifs) == 1 # Got the reassign notification

def test_unassign_records_audit_no_notification(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    assignee = users_and_task["other"]
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee.email)

    # Unassign
    collaboration_service.unassign_task(task_id, owner_id)

    with _get_new_session() as verify_session:
        audits = verify_session.execute(sa.select(AuditLogORM).where(AuditLogORM.task_id == task_id)).scalars().all()
        unassign_audits = [a for a in audits if a.action == "unassign"]
        assert len(unassign_audits) == 1

        # Should not have created a new notification
        notifs = verify_session.execute(sa.select(NotificationORM).where(NotificationORM.recipient_id == assignee.id)).scalars().all()
        assert len(notifs) == 1 # Just the original assign

def test_same_assignee_idempotent(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    assignee = users_and_task["other"]
    task_id = users_and_task["task"].id

    collaboration_service.assign_task(task_id, owner_id, assignee.email)

    with _get_new_session() as verify_session:
        audits_before = verify_session.execute(sa.select(sa.func.count(AuditLogORM.id)).where(AuditLogORM.task_id == task_id)).scalar()
        notifs_before = verify_session.execute(sa.select(sa.func.count(NotificationORM.id)).where(NotificationORM.recipient_id == assignee.id)).scalar()

    # Reassign to same
    collaboration_service.assign_task(task_id, owner_id, assignee.email)

    with _get_new_session() as verify_session:
        audits_after = verify_session.execute(sa.select(sa.func.count(AuditLogORM.id)).where(AuditLogORM.task_id == task_id)).scalar()
        notifs_after = verify_session.execute(sa.select(sa.func.count(NotificationORM.id)).where(NotificationORM.recipient_id == assignee.id)).scalar()

    assert audits_after == audits_before
    assert notifs_after == notifs_before

def test_reject_self_assignment_and_nonexistent(collaboration_service, users_and_task):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    owner_email = users_and_task["owner"].email

    with pytest.raises(ValidationError):
        collaboration_service.assign_task(task_id, owner_id, owner_email)

    with pytest.raises(ValidationError):
        collaboration_service.assign_task(task_id, owner_id, "nobody@example.com")

def test_manage_assignments_only_owner(collaboration_service, users_and_task):
    other_id = users_and_task["other"].id
    third_email = users_and_task["third"].email
    task_id = users_and_task["task"].id

    with pytest.raises(TaskNotAccessibleError):
        collaboration_service.assign_task(task_id, other_id, third_email)

    with pytest.raises(TaskNotAccessibleError):
        collaboration_service.unassign_task(task_id, other_id)

def test_reject_operations_on_deleted_task(collaboration_service, users_and_task, task_repo, db_session):
    owner_id = users_and_task["owner"].id
    task_id = users_and_task["task"].id
    assignee_email = users_and_task["other"].email

    task_repo.soft_delete(task_id, owner_id, "2026-10-05T00:00:00Z")
    db_session.commit()

    with pytest.raises(TaskNotAccessibleError):
        collaboration_service.assign_task(task_id, owner_id, assignee_email)

def test_concurrency_protection(collaboration_service, users_and_task, task_repo):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["other"].email
    task_id = users_and_task["task"].id

    # Mock task_repo.set_assignee to simulate 0 rowcount (concurrency)
    with patch.object(task_repo, 'set_assignee', return_value=False):
        with pytest.raises(ConflictError):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)
