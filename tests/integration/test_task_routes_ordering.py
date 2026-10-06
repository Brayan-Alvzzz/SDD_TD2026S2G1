import pytest

def seed_users_and_tasks(user_service, task_service, task_repo):
    user_owner = user_service.register_user("owner@test.com", "password123")
    user_other = user_service.register_user("other@test.com", "password123")

    t1 = task_service.create_task(user_owner.id, "T1")
    t2 = task_service.create_task(user_owner.id, "T2")
    t3 = task_service.create_task(user_owner.id, "T3")
    task_repo.set_assignee(t3.id, None, user_other.id)
    
    t_other = task_service.create_task(user_other.id, "T_Other")
    t_assigned = task_service.create_task(user_other.id, "T_Assigned")
    task_repo.set_assignee(t_assigned.id, None, user_owner.id)

    t_del = task_service.create_task(user_owner.id, "T_Del")
    task_service.delete_task(t_del.id, user_owner.id)

    return user_owner, user_other, t1, t2, t3, t_other, t_assigned, t_del


def test_order_tasks_success_and_idempotence(client, user_service, task_service, task_repo):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    res = client.patch("/api/tasks/order", json={"task_ids": [t3.id, t1.id, t2.id]})
    # Fallará porque no existe la ruta
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "success"
    assert data["changed"] == 3
    
    # Idempotencia
    res2 = client.patch("/api/tasks/order", json={"task_ids": [t3.id, t1.id, t2.id]})
    assert res2.status_code == 200
    assert res2.get_json()["changed"] == 0


def test_order_tasks_unauthenticated(client):
    res = client.patch("/api/tasks/order", json={"task_ids": [1, 2]})
    assert res.status_code == 401


def test_order_tasks_invalid_structure(client, user_service, task_service, task_repo):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    # Not JSON
    res = client.patch("/api/tasks/order", data="not-json")
    assert res.status_code == 400
    
    # Missing key
    res = client.patch("/api/tasks/order", json={"ids": [t1.id]})
    assert res.status_code == 400
    
    # Not a list
    res = client.patch("/api/tasks/order", json={"task_ids": t1.id})
    assert res.status_code == 400
    
    # Boolean as ID
    res = client.patch("/api/tasks/order", json={"task_ids": [True, False]})
    assert res.status_code == 400
    
    # Duplicates
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t1.id, t2.id, t3.id]})
    assert res.status_code == 400


def test_order_tasks_operation_not_permitted(client, user_service, task_service, task_repo):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    # Attempt to order t_assigned which belongs to other
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t2.id, t3.id, t_assigned.id]})
    assert res.status_code == 403


def test_order_tasks_not_found(client, user_service, task_service, task_repo):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    # Alien task
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t2.id, t_other.id]})
    assert res.status_code == 404
    
    # Deleted task
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t2.id, t_del.id]})
    assert res.status_code == 404
    
    # Nonexistent task
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t2.id, 9999]})
    assert res.status_code == 404


def test_order_tasks_conflict(client, user_service, task_service, task_repo):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    # Missing t3
    res = client.patch("/api/tasks/order", json={"task_ids": [t1.id, t2.id]})
    assert res.status_code == 409
    
    # Empty list when tasks exist
    res = client.patch("/api/tasks/order", json={"task_ids": []})
    assert res.status_code == 409


def test_order_tasks_empty_success(client, user_service, task_service):
    owner = user_service.register_user("empty@test.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
        
    res = client.patch("/api/tasks/order", json={"task_ids": []})
    assert res.status_code == 200
    assert res.get_json()["changed"] == 0


def test_task_list_orders_by_position(client, user_service, task_service, task_repo, db_session):
    owner, other, t1, t2, t3, t_other, t_assigned, t_del = seed_users_and_tasks(user_service, task_service, task_repo)
    
    # Simulamos el orden para que la ruta /api/tasks (o similar) deba devolverlo
    task_service.update_task_order(owner.id, [t3.id, t2.id, t1.id])
    
    with client.session_transaction() as sess:
        sess["user_id"] = owner.id
        sess["user_email"] = owner.email
    
    # API role=owned (or default view)
    res = client.get("/api/tasks?role=owned")
    assert res.status_code == 200
    tasks = res.get_json()["tasks"]
    
    # Verify the items returned belong to owner
    # Then verify the order matches the position
    owner_task_ids = [t["id"] for t in tasks]
    assert owner_task_ids == [t3.id, t2.id, t1.id]
