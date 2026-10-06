import pytest
from unittest.mock import patch
from src.infrastructure.models import TaskORM
from src.domain.exceptions import ConflictError

@pytest.fixture
def users_and_task(user_repo, task_repo, db_session):
    owner = user_repo.create("owner@example.com", "hash")
    assignee = user_repo.create("assignee@example.com", "hash")
    stranger = user_repo.create("stranger@example.com", "hash")
    task = task_repo.create(owner.id, "Test Task")
    db_session.commit()
    return {"owner": owner, "assignee": assignee, "stranger": stranger, "task": task}

def _login(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["user_email"] = user.email

def test_assign_task_as_owner_success(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    _login(client, owner)

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    assert resp.status_code == 200
    data = resp.json
    assert data["success"] is True
    assert data["data"]["task_id"] == task.id
    assert data["data"]["changed"] is True
    assert data["data"]["action"] == "assign"
    assert data["data"]["assignee"]["email"] == assignee.email

def test_reassign_task_as_owner(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    _login(client, owner)

    client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": stranger.email})
    assert resp.status_code == 200
    data = resp.json
    assert data["data"]["changed"] is True
    assert data["data"]["action"] == "reassign"
    assert data["data"]["assignee"]["email"] == stranger.email

def test_unassign_task_as_owner(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    _login(client, owner)

    client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})

    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 200
    data = resp.json
    assert data["data"]["changed"] is True
    assert data["data"]["action"] == "unassign"
    assert data["data"]["assignee"] is None

def test_assign_idempotent(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    _login(client, owner)

    client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    assert resp.status_code == 200
    data = resp.json
    assert data["data"]["changed"] is False
    assert data["data"]["action"] == "none"

def test_unassign_idempotent(client, users_and_task):
    owner = users_and_task["owner"]
    task = users_and_task["task"]
    _login(client, owner)

    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 200
    data = resp.json
    assert data["data"]["changed"] is False
    assert data["data"]["action"] == "none"

def test_reject_nonexistent_and_self_assignment(client, users_and_task):
    owner = users_and_task["owner"]
    task = users_and_task["task"]
    _login(client, owner)

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": "nobody@example.com"})
    assert resp.status_code == 400
    assert resp.json["success"] is False

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": owner.email})
    assert resp.status_code == 400
    assert resp.json["success"] is False

def test_invalid_input(client, users_and_task):
    owner = users_and_task["owner"]
    task = users_and_task["task"]
    _login(client, owner)

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={})
    assert resp.status_code == 400

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": ""})
    assert resp.status_code == 400

def test_401_no_session(client, users_and_task):
    task = users_and_task["task"]
    assignee = users_and_task["assignee"]

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    assert resp.status_code == 401

    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 401

def test_403_assignee_cannot_manage(client, users_and_task):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    stranger = users_and_task["stranger"]
    task = users_and_task["task"]
    
    _login(client, owner)
    client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})

    _login(client, assignee)
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": stranger.email})
    assert resp.status_code == 403

    resp = client.delete(f"/api/tasks/{task.id}/assignee")
    assert resp.status_code == 403

def test_404_stranger(client, users_and_task):
    stranger = users_and_task["stranger"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    _login(client, stranger)

    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    assert resp.status_code == 404

def test_404_deleted_task(client, users_and_task, task_repo, db_session):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    
    task_repo.soft_delete(task.id, owner.id, "2026-10-05T00:00:00Z")
    db_session.commit()

    _login(client, owner)
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
    assert resp.status_code == 404

def test_409_concurrency(client, users_and_task, task_repo):
    owner = users_and_task["owner"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    _login(client, owner)

    with patch.object(task_repo.__class__, 'set_assignee', return_value=False):
        resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email})
        assert resp.status_code == 409

def test_actor_from_session_cannot_spoof(client, users_and_task):
    owner = users_and_task["owner"]
    stranger = users_and_task["stranger"]
    assignee = users_and_task["assignee"]
    task = users_and_task["task"]
    
    _login(client, stranger)
    # Stranger tries to pass owner's ID
    resp = client.put(f"/api/tasks/{task.id}/assignee", json={"assignee_email": assignee.email, "actor_id": owner.id, "user_id": owner.id})
    assert resp.status_code == 404 # Still evaluated as stranger
