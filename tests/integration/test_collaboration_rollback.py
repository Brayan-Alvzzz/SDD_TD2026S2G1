import pytest
from unittest.mock import patch
from sqlalchemy.orm import sessionmaker
from src.domain.services import CollaborationService
from src.infrastructure.repositories import NotificationRepository
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
    assignee = user_repo.create("assignee@example.com", "hash")
    task = task_repo.create(owner.id, "Test Task Rollback")
    db_session.commit()
    return {"owner": owner, "assignee": assignee, "task": task}

def _get_new_session():
    Session = sessionmaker(bind=db.engine)
    return Session()

def test_rollback_if_audit_fails(collaboration_service, users_and_task, task_repo, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["assignee"].email
    task_id = users_and_task["task"].id

    audits_before = len(audit_repo.list_by_task(task_id))
    notifs_before = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))

    with patch.object(audit_repo, 'create', side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)

    # We don't rollback the test session. The service should have rolled back its transaction.

    with _get_new_session() as verify_session:
        task_orm = verify_session.get(TaskORM, task_id)
        assert task_orm.assignee_id is None, "Task assignee should not be updated"

        audits_after = verify_session.execute(sa.select(sa.func.count(AuditLogORM.id)).where(AuditLogORM.task_id == task_id)).scalar()
        assert audits_after == audits_before, "No audit log should be created"

        notifs_after = verify_session.execute(sa.select(sa.func.count(NotificationORM.id)).where(NotificationORM.recipient_id == users_and_task["assignee"].id)).scalar()
        assert notifs_after == notifs_before, "No notification should be created"

def test_rollback_if_notification_fails(collaboration_service, users_and_task, task_repo, audit_repo, notification_repo, db_session):
    owner_id = users_and_task["owner"].id
    assignee_email = users_and_task["assignee"].email
    task_id = users_and_task["task"].id

    audits_before = len(audit_repo.list_by_task(task_id))
    notifs_before = len(notification_repo.list_by_recipient(users_and_task["assignee"].id))

    with patch.object(notification_repo, 'create', side_effect=Exception("Notif DB Error")):
        with pytest.raises(Exception, match="Notif DB Error"):
            collaboration_service.assign_task(task_id, owner_id, assignee_email)

    with _get_new_session() as verify_session:
        task_orm = verify_session.get(TaskORM, task_id)
        assert task_orm.assignee_id is None, "Task assignee should not be updated"

        audits_after = verify_session.execute(sa.select(sa.func.count(AuditLogORM.id)).where(AuditLogORM.task_id == task_id)).scalar()
        assert audits_after == audits_before, "Audit log should be rolled back"

        notifs_after = verify_session.execute(sa.select(sa.func.count(NotificationORM.id)).where(NotificationORM.recipient_id == users_and_task["assignee"].id)).scalar()
        assert notifs_after == notifs_before, "No notification should be created"
