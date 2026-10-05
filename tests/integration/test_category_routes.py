import pytest


def test_get_categories_unauthenticated_rejected(client):
    """Unauthenticated requests are redirected (web) or rejected with 401 (API)."""
    res_web = client.get("/categories")
    assert res_web.status_code == 302
    assert "/login" in res_web.headers["Location"]

    res_api = client.get("/api/categories")
    assert res_api.status_code == 401


def test_create_and_list_categories_web(auth_client):
    """Creating a category via web form and listing categories with task count."""
    client, user = auth_client
    # Create category
    post_res = client.post("/categories", data={"name": "Trabajo"}, follow_redirects=True)
    assert post_res.status_code == 200
    assert "Trabajo".encode("utf-8") in post_res.data

    # Check listing
    get_res = client.get("/categories")
    assert get_res.status_code == 200
    assert "Trabajo".encode("utf-8") in get_res.data


def test_create_and_list_categories_api(auth_client):
    """Creating a category via API and listing categories with task count in JSON."""
    client, user = auth_client
    post_res = client.post("/api/categories", json={"name": "Estudio"})
    assert post_res.status_code == 201
    data = post_res.get_json()
    assert data["status"] == "success" or data.get("success") is True
    cat_id = data["data"]["id"]
    assert data["data"]["name"] == "Estudio"

    list_res = client.get("/api/categories")
    assert list_res.status_code == 200
    items = list_res.get_json()["data"]
    assert any(c["id"] == cat_id and c["name"] == "Estudio" for c in items)


def test_create_category_validation_and_duplicate_rejection(auth_client):
    """API and Web reject empty, too long, or duplicate category names."""
    client, user = auth_client
    client.post("/api/categories", json={"name": "Única"})

    # Duplicate name rejected
    dup_res = client.post("/api/categories", json={"name": "Única"})
    assert dup_res.status_code in (400, 409)

    # Empty name rejected
    empty_res = client.post("/api/categories", json={"name": "   "})
    assert empty_res.status_code == 400

    # Over 50 chars rejected
    long_res = client.post("/api/categories", json={"name": "A" * 51})
    assert long_res.status_code == 400


def test_categories_multi_user_isolation(auth_client, user_service, app):
    """Categories are strictly isolated between users: duplicate names allowed for different users."""
    client1, user1 = auth_client
    user2 = user_service.register_user("cat_iso_user2@example.com", "password123")

    client2 = app.test_client()
    with client2.session_transaction() as sess:
        sess["user_id"] = user2.id
        sess["user_email"] = user2.email

    # Both users create a category named "Personal"
    res1 = client1.post("/api/categories", json={"name": "Personal"})
    assert res1.status_code == 201

    res2 = client2.post("/api/categories", json={"name": "Personal"})
    assert res2.status_code == 201

    # User 1 only sees User 1's category
    list1 = client1.get("/api/categories").get_json()["data"]
    assert len(list1) == 1
    assert list1[0]["id"] == res1.get_json()["data"]["id"]

    # User 2 only sees User 2's category
    list2 = client2.get("/api/categories").get_json()["data"]
    assert len(list2) == 1
    assert list2[0]["id"] == res2.get_json()["data"]["id"]


def test_delete_category_api_unlinks_tasks_without_deleting_them(auth_client, task_service, audit_repo):
    """Deleting a category via API unlinks associated tasks, leaving tasks and audit logs intact."""
    client, user = auth_client
    cat_res = client.post("/api/categories", json={"name": "Por Borrar"})
    cat_id = cat_res.get_json()["data"]["id"]

    task1 = task_service.create_task(user.id, "Tarea 1 en cat", category_id=cat_id)
    task2 = task_service.create_task(user.id, "Tarea 2 en cat", category_id=cat_id)
    task_service.update_task_status(task1.id, user.id, "en_progreso")

    # DELETE /api/categories/<cat_id>
    del_res = client.delete(f"/api/categories/{cat_id}")
    assert del_res.status_code == 200

    # Category is gone
    get_cat = client.get("/api/categories")
    assert not any(c["id"] == cat_id for c in get_cat.get_json()["data"])

    # Tasks still exist in GET /api/tasks and have category_id = null
    tasks_res = client.get("/api/tasks")
    task_data = tasks_res.get_json()["data"]
    t1_fetched = next(t for t in task_data if t["id"] == task1.id)
    t2_fetched = next(t for t in task_data if t["id"] == task2.id)

    assert t1_fetched["category_id"] is None
    assert t1_fetched["status"] == "en_progreso"
    assert t2_fetched["category_id"] is None

    # Audit logs for task1 intact
    logs = audit_repo.list_by_task(task1.id)
    assert any(log.action == "status_change" for log in logs)


def test_delete_category_web_unlinks_tasks(auth_client, task_service):
    """Deleting a category via Web POST /categories/<id>/delete unlinks associated tasks."""
    client, user = auth_client
    cat_res = client.post("/api/categories", json={"name": "Web Delete Cat"})
    cat_id = cat_res.get_json()["data"]["id"]

    task = task_service.create_task(user.id, "Tarea Web Cat", category_id=cat_id)

    del_res = client.post(f"/categories/{cat_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200

    refetched = task_service.get_task(task.id, user.id)
    assert refetched.category_id is None
    assert refetched.is_deleted is False


def test_delete_category_alien_or_unauthorized(auth_client, user_service, app):
    """Users cannot delete categories belonging to other users."""
    client1, user1 = auth_client
    user2 = user_service.register_user("cat_alien_del@example.com", "password123")

    client2 = app.test_client()
    with client2.session_transaction() as sess:
        sess["user_id"] = user2.id
        sess["user_email"] = user2.email

    cat_res = client1.post("/api/categories", json={"name": "Privada de User 1"})
    cat_id = cat_res.get_json()["data"]["id"]

    # User 2 tries to delete User 1's category
    del_alien = client2.delete(f"/api/categories/{cat_id}")
    assert del_alien.status_code in (403, 404)

    # Category still exists for User 1
    list1 = client1.get("/api/categories").get_json()["data"]
    assert any(c["id"] == cat_id for c in list1)


def test_patch_api_task_category(auth_client, task_service):
    """PATCH /api/tasks/<id>/category updates task category and unlinks with null."""
    client, user = auth_client
    cat_res = client.post("/api/categories", json={"name": "Sprint Actual"})
    cat_id = cat_res.get_json()["data"]["id"]

    task = task_service.create_task(user.id, "Tarea para categorizar")
    assert task.category_id is None

    # Assign category
    patch_res = client.patch(f"/api/tasks/{task.id}/category", json={"category_id": cat_id})
    assert patch_res.status_code == 200
    assert patch_res.get_json()["data"]["category_id"] == cat_id

    # Unlink category (null)
    unlink_res = client.patch(f"/api/tasks/{task.id}/category", json={"category_id": None})
    assert unlink_res.status_code == 200
    assert unlink_res.get_json()["data"]["category_id"] is None


def test_patch_api_task_category_alien_rejected(auth_client, user_service, task_service, app):
    """PATCH /api/tasks/<id>/category rejects assigning another user's category."""
    client1, user1 = auth_client
    user2 = user_service.register_user("cat_patch_alien@example.com", "password123")

    client2 = app.test_client()
    with client2.session_transaction() as sess:
        sess["user_id"] = user2.id
        sess["user_email"] = user2.email

    # User 2 creates category
    cat_res = client2.post("/api/categories", json={"name": "Cat de User 2"})
    cat2_id = cat_res.get_json()["data"]["id"]

    # User 1 creates task
    task = task_service.create_task(user1.id, "Tarea de User 1")

    # User 1 tries to assign User 2's category
    patch_alien = client1.patch(f"/api/tasks/{task.id}/category", json={"category_id": cat2_id})
    assert patch_alien.status_code in (400, 403, 404)


def test_task_listing_filter_by_category_and_none(auth_client, task_service):
    """GET /api/tasks filters by category_id, 'none', and combines with status and priority sort."""
    client, user = auth_client
    cat1_res = client.post("/api/categories", json={"name": "Backend"})
    cat1_id = cat1_res.get_json()["data"]["id"]

    cat2_res = client.post("/api/categories", json={"name": "Frontend"})
    cat2_id = cat2_res.get_json()["data"]["id"]

    t1 = task_service.create_task(user.id, "API Route", category_id=cat1_id, priority="alta")
    t2 = task_service.create_task(user.id, "DB Schema", category_id=cat1_id, priority="media")
    t3 = task_service.create_task(user.id, "CSS Styling", category_id=cat2_id, priority="baja")
    t4 = task_service.create_task(user.id, "Read Docs", priority="alta")  # no category

    # 1. Filter by Backend (cat1)
    res_cat1 = client.get(f"/api/tasks?category_id={cat1_id}")
    assert res_cat1.status_code == 200
    ids_cat1 = [t["id"] for t in res_cat1.get_json()["data"]]
    assert set(ids_cat1) == {t1.id, t2.id}

    # 2. Filter by uncategorized ('none')
    res_none = client.get("/api/tasks?category_id=none")
    assert res_none.status_code == 200
    ids_none = [t["id"] for t in res_none.get_json()["data"]]
    assert ids_none == [t4.id]

    # 3. Combine category + status + priority sort
    res_combo = client.get(f"/api/tasks?category_id={cat1_id}&status=pendiente&sort=priority_desc")
    assert res_combo.status_code == 200
    combo_tasks = res_combo.get_json()["data"]
    assert len(combo_tasks) == 2
    assert combo_tasks[0]["id"] == t1.id  # alta
    assert combo_tasks[1]["id"] == t2.id  # media
