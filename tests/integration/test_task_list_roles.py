import pytest
from src.infrastructure.models import TaskORM
from src.domain.services import CollaborationService
from src.infrastructure.repositories import AuditLogRepository, NotificationRepository
from src.infrastructure.repositories import TaskRepository

def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id

@pytest.fixture
def users_and_tasks(db_session, user_repo, task_repo, category_repo):
    owner = user_repo.create("owner@example.com", "hash")
    assignee = user_repo.create("assignee@example.com", "hash")
    stranger = user_repo.create("stranger@example.com", "hash")
    stranger2 = user_repo.create("stranger2@example.com", "hash")
    
    db_session.commit()
    
    cat1 = category_repo.create(owner.id, "Cat1")
    db_session.commit()

    # t1: owned by owner, unassigned
    t1 = task_repo.create(owner.id, "t1", status="pendiente", priority="alta")
    # t2: owned by owner, assigned to assignee
    t2 = task_repo.create(owner.id, "t2", status="en_progreso", priority="media")
    # t3: owned by stranger, assigned to owner
    t3 = task_repo.create(stranger.id, "t3", status="pendiente", priority="baja")
    # t4: owned by stranger, unassigned
    t4 = task_repo.create(stranger.id, "t4", status="completada", priority="media")
    # t5: owned by owner, assigned to assignee, deleted
    t5 = task_repo.create(owner.id, "t5", status="pendiente", priority="media")
    # t6: owned by owner, unassigned, in cat1
    t6 = task_repo.create(owner.id, "t6", status="pendiente", priority="alta", category_id=cat1.id)
    
    db_session.commit()
    
    collab_service = CollaborationService(
        task_repo=task_repo,
        user_repo=user_repo,
        audit_repo=AuditLogRepository(db_session),
        notification_repo=NotificationRepository(db_session),
        session=db_session
    )

    collab_service.assign_task(t2.id, owner.id, assignee.email)
    collab_service.assign_task(t3.id, stranger.id, owner.email)
    collab_service.assign_task(t5.id, owner.id, assignee.email)
    
    task_repo.soft_delete(t5.id, owner.id, "2026-10-05T00:00:00Z")
    db_session.commit()

    return {
        "owner": owner,
        "assignee": assignee,
        "stranger": stranger,
        "stranger2": stranger2,
        "cat1": cat1,
        "t1": t1,
        "t2": t2,
        "t3": t3,
        "t4": t4,
        "t5": t5,
        "t6": t6
    }

def test_list_all_tasks_owner(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    _login(client, owner)
    
    resp = client.get("/api/tasks?role=all")
    assert resp.status_code == 200
    data = resp.json["data"]
    
    ids = {t["id"] for t in data}
    assert users_and_tasks["t1"].id in ids
    assert users_and_tasks["t2"].id in ids
    assert users_and_tasks["t3"].id in ids
    assert users_and_tasks["t4"].id not in ids
    assert users_and_tasks["t5"].id not in ids
    assert users_and_tasks["t6"].id in ids
    assert len(ids) == 4

    # Check response fields for t2
    t2_data = next(t for t in data if t["id"] == users_and_tasks["t2"].id)
    assert t2_data["viewer_role"] == "owner"
    assert t2_data["owner"]["id"] == owner.id
    assert t2_data["assignee"]["id"] == users_and_tasks["assignee"].id

def test_list_role_filters(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    _login(client, owner)
    
    # role=owned
    resp = client.get("/api/tasks?role=owned")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {users_and_tasks["t1"].id, users_and_tasks["t2"].id, users_and_tasks["t6"].id}

    # role=assigned_to_me
    resp = client.get("/api/tasks?role=assigned_to_me")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {users_and_tasks["t3"].id}

    # role=delegated
    resp = client.get("/api/tasks?role=delegated")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {users_and_tasks["t2"].id}

def test_list_invalid_role(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    _login(client, owner)
    resp = client.get("/api/tasks?role=invalid")
    assert resp.status_code == 400

def test_list_combination_filters(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    _login(client, owner)
    
    # status=en_progreso
    resp = client.get("/api/tasks?role=all&status=en_progreso")
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {users_and_tasks["t2"].id}

    # sort=priority_desc
    resp = client.get("/api/tasks?role=all&sort=priority_desc")
    data = resp.json["data"]
    priorities = [t["priority"] for t in data]
    assert priorities == ["alta", "alta", "media", "baja"] # t1, t6, t2, t3

def test_assignee_visibility(client, users_and_tasks, db_session, user_repo, task_repo):
    assignee = users_and_tasks["assignee"]
    owner = users_and_tasks["owner"]
    t2 = users_and_tasks["t2"]
    
    collab_service = CollaborationService(
        task_repo=task_repo,
        user_repo=user_repo,
        audit_repo=AuditLogRepository(db_session),
        notification_repo=NotificationRepository(db_session),
        session=db_session
    )
    
    _login(client, assignee)
    
    # Assignee sees t2
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {t2.id}
    
    # Check viewer_role
    t2_data = resp.json["data"][0]
    assert t2_data["viewer_role"] == "assignee"
    
    # Unassign t2
    collab_service.unassign_task(t2.id, owner.id)
    
    # Assignee no longer sees t2
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert len(ids) == 0

    # Owner still sees t2
    _login(client, owner)
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert t2.id in ids

def test_list_category_filter(client, users_and_tasks):
    owner = users_and_tasks["owner"]
    cat1 = users_and_tasks["cat1"]
    _login(client, owner)
    
    resp = client.get(f"/api/tasks?role=all&category_id={cat1.id}")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json["data"]}
    assert ids == {users_and_tasks["t6"].id}

def test_reassignment_visibility(client, users_and_tasks, db_session, user_repo, task_repo):
    owner = users_and_tasks["owner"]
    assignee = users_and_tasks["assignee"]
    stranger2 = users_and_tasks["stranger2"]
    t2 = users_and_tasks["t2"]

    collab_service = CollaborationService(
        task_repo=task_repo,
        user_repo=user_repo,
        audit_repo=AuditLogRepository(db_session),
        notification_repo=NotificationRepository(db_session),
        session=db_session
    )

    # Reassign t2 from assignee to stranger2
    collab_service.assign_task(t2.id, owner.id, stranger2.email)

    # Assignee loses visibility
    _login(client, assignee)
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert t2.id not in ids

    # Stranger2 gains visibility
    _login(client, stranger2)
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert t2.id in ids

    # Owner keeps visibility
    _login(client, owner)
    resp = client.get("/api/tasks?role=all")
    ids = {t["id"] for t in resp.json["data"]}
    assert t2.id in ids

