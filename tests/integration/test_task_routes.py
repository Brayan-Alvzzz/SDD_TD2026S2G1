def test_unauthenticated_user_redirected(client):
    res = client.get("/tasks", follow_redirects=False)
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_empty_tasks_view(auth_client):
    client, user = auth_client
    res = client.get("/tasks")
    assert res.status_code == 200
    assert "No tienes tareas registradas".encode("utf-8") in res.data
    assert "Crear mi primera tarea".encode("utf-8") in res.data


def test_create_task_and_list_flow(auth_client):
    client, user = auth_client
    # Create Task
    create_res = client.post("/tasks", data={
        "title": "Aprender Spec-Driven Development",
        "description": "Estudiar la constitución y los comandos",
        "due_date": "2026-10-30"
    }, follow_redirects=True)
    assert create_res.status_code == 200
    assert "Aprender Spec-Driven Development".encode("utf-8") in create_res.data
    assert "pendiente".encode("utf-8") in create_res.data


def test_create_task_validation_error(auth_client):
    client, user = auth_client
    res = client.post("/tasks", data={
        "title": "   ",
        "description": "Sin título"
    }, follow_redirects=True)
    assert res.status_code == 400
    assert "obligatorio".encode("utf-8") in res.data


def test_multi_user_isolation(client, user_service):
    # Register User A and create task
    user_a = user_service.register_user("user_a@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_a.id
        sess["user_email"] = user_a.email

    client.post("/tasks", data={"title": "Tarea Privada de A"})

    # Switch to User B
    user_b = user_service.register_user("user_b@example.com", "password123")
    with client.session_transaction() as sess:
        sess["user_id"] = user_b.id
        sess["user_email"] = user_b.email

    res = client.get("/tasks")
    assert res.status_code == 200
    # User B must NOT see User A's task
    assert "Tarea Privada de A".encode("utf-8") not in res.data


def test_api_tasks_get_json(auth_client):
    client, user = auth_client
    client.post("/tasks", data={"title": "Tarea API 1"})
    res = client.get("/api/tasks")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["success"] is True
    assert len(json_data["data"]) == 1
    assert json_data["data"][0]["title"] == "Tarea API 1"


def test_api_patch_task_status_transition_and_audit(auth_client, audit_repo):
    client, user = auth_client
    # Create task
    create_res = client.post("/tasks", json={"title": "Tarea para avanzar"})
    task_id = create_res.get_json()["data"]["id"]

    # Transition to en_progreso
    patch_res = client.patch(f"/api/tasks/{task_id}/status", json={"status": "en_progreso"})
    assert patch_res.status_code == 200
    assert patch_res.get_json()["data"]["status"] == "en_progreso"

    # Transition to completada
    patch_res2 = client.patch(f"/api/tasks/{task_id}/status", json={"status": "completada"})
    assert patch_res2.status_code == 200
    assert patch_res2.get_json()["data"]["status"] == "completada"

    # Illegal transition: completada -> pendiente
    illegal_res = client.patch(f"/api/tasks/{task_id}/status", json={"status": "pendiente"})
    assert illegal_res.status_code == 400
    assert "reapertura explícita" in illegal_res.get_json()["error"]

    # Check audit log entries (create + 2 status changes)
    logs = audit_repo.list_by_task(task_id)
    assert len(logs) == 3
    assert logs[1].action == "status_change"
    assert logs[2].action == "status_change"


def test_edit_task_view_and_post_update(auth_client, audit_repo):
    client, user = auth_client
    # Create task
    create_res = client.post("/tasks", data={"title": "Tarea Original"})
    # Fetch ID from DB or list
    list_res = client.get("/api/tasks")
    task_id = list_res.get_json()["data"][0]["id"]

    # GET edit view
    edit_page = client.get(f"/tasks/{task_id}/edit")
    assert edit_page.status_code == 200
    assert "Editar Tarea".encode("utf-8") in edit_page.data

    # POST edit update
    post_res = client.post(f"/tasks/{task_id}/edit", data={
        "title": "Tarea Renombrada",
        "description": "Nueva nota",
        "due_date": "2026-12-31"
    }, follow_redirects=True)
    assert post_res.status_code == 200
    assert "Tarea Renombrada".encode("utf-8") in post_res.data

    # Check audit update log
    logs = audit_repo.list_by_task(task_id)
    assert any(log.action == "update" for log in logs)


def test_edit_task_put_api(auth_client):
    client, user = auth_client
    create_res = client.post("/tasks", json={"title": "Tarea PUT Inicial"})
    task_id = create_res.get_json()["data"]["id"]

    put_res = client.put(f"/api/tasks/{task_id}", json={
        "title": "Tarea PUT Actualizada",
        "description": "Nota agregada",
        "due_date": "2026-11-11"
    })
    assert put_res.status_code == 200
    assert put_res.get_json()["data"]["title"] == "Tarea PUT Actualizada"


def test_soft_delete_web_route_success(auth_client, audit_repo):
    client, user = auth_client
    # Create task
    create_res = client.post("/tasks", data={"title": "Tarea para Borrado Web"})
    list_res = client.get("/api/tasks")
    task_id = list_res.get_json()["data"][0]["id"]

    # POST /tasks/<id>/delete
    del_res = client.post(f"/tasks/{task_id}/delete", follow_redirects=False)
    assert del_res.status_code == 302
    assert "/tasks" in del_res.headers["Location"]

    # Verify task disappeared from list view
    tasks_page = client.get("/tasks")
    assert "Tarea para Borrado Web".encode("utf-8") not in tasks_page.data

    # Verify task is deleted in audit logs
    logs = audit_repo.list_by_task(task_id)
    assert any(log.action == "delete" for log in logs)


def test_soft_delete_api_route_success(auth_client):
    client, user = auth_client
    create_res = client.post("/tasks", json={"title": "Tarea para DELETE API"})
    task_id = create_res.get_json()["data"]["id"]

    # DELETE /api/tasks/<id>
    del_res = client.delete(f"/api/tasks/{task_id}")
    assert del_res.status_code == 200
    json_data = del_res.get_json()
    assert json_data["status"] == "success"
    assert json_data["data"]["id"] == task_id
    assert json_data["data"]["is_deleted"] is True

    # Verify subsequent GET /api/tasks does not contain it
    list_res = client.get("/api/tasks")
    task_ids = [t["id"] for t in list_res.get_json()["data"]]
    assert task_id not in task_ids


def test_soft_delete_unauthenticated_rejected(client):
    # Web endpoint requires login -> redirect 302 to /login
    web_res = client.post("/tasks/1/delete", follow_redirects=False)
    assert web_res.status_code == 302
    assert "/login" in web_res.headers["Location"]

    # API endpoint requires login -> 401
    api_res = client.delete("/api/tasks/1")
    assert api_res.status_code == 401


def test_soft_delete_nonexistent_or_already_deleted_or_alien(auth_client, user_service, task_service):
    client, user = auth_client

    # 1. Nonexistent task
    del_res = client.post("/tasks/99999/delete")
    assert del_res.status_code == 404
    api_del_res = client.delete("/api/tasks/99999")
    assert api_del_res.status_code == 404

    # 2. Alien task (belongs to another user)
    alien_user = user_service.register_user("alien_user@example.com", "password123")
    alien_task = task_service.create_task(alien_user.id, "Tarea de Otro")
    alien_web_res = client.post(f"/tasks/{alien_task.id}/delete")
    assert alien_web_res.status_code == 404
    alien_api_res = client.delete(f"/api/tasks/{alien_task.id}")
    assert alien_api_res.status_code == 404

    # 3. Already deleted task
    own_task = task_service.create_task(user.id, "Tarea Propia a Borrar")
    client.post(f"/tasks/{own_task.id}/delete")

    dup_web_res = client.post(f"/tasks/{own_task.id}/delete")
    assert dup_web_res.status_code == 404
    dup_api_res = client.delete(f"/api/tasks/{own_task.id}")
    assert dup_api_res.status_code == 404


def test_deleted_task_cannot_be_opened_in_edit_view(auth_client, task_service):
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea que sera eliminada")
    task_service.delete_task(task.id, user.id)

    # Direct GET to /tasks/<id>/edit must return 404
    get_res = client.get(f"/tasks/{task.id}/edit")
    assert get_res.status_code == 404
    assert "Editar Tarea".encode("utf-8") not in get_res.data

    # Direct POST to /tasks/<id>/edit must return 404 and reject modification
    post_res = client.post(f"/tasks/{task.id}/edit", data={"title": "Intento de Modificacion"})
    assert post_res.status_code == 404


def test_deleted_task_status_change_via_api_returns_controlled_error(auth_client, task_service):
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea para prueba de estado")
    task_service.delete_task(task.id, user.id)

    # Attempting to change status of deleted task via API
    res = client.patch(f"/api/tasks/{task.id}/status", json={"status": "en_progreso"})
    # Must be controlled error (400 or 404), NEVER 500
    assert res.status_code in (400, 404)
    assert res.status_code != 500
    json_data = res.get_json()
    assert json_data["success"] is False
    assert "error" in json_data


def test_reopen_task_web_route_success(auth_client, task_service, audit_repo):
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea para Reabrir Web")
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")

    res = client.post(f"/tasks/{task.id}/reopen", follow_redirects=False)
    assert res.status_code == 302
    assert "/tasks" in res.headers["Location"]

    # Verify task status is now 'pendiente'
    reopened = task_service.get_task(task.id, user.id)
    assert reopened.status == "pendiente"

    # Verify audit log contains reopen
    logs = audit_repo.list_by_task(task.id)
    assert logs[-1].action == "reopen"


def test_reopen_task_api_route_success(auth_client, task_service):
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea para Reabrir API")
    task_service.update_task_status(task.id, user.id, "en_progreso")
    task_service.update_task_status(task.id, user.id, "completada")

    res = client.post(f"/api/tasks/{task.id}/reopen")
    assert res.status_code == 200
    json_data = res.get_json()
    assert json_data["status"] == "success"
    assert json_data["data"]["id"] == task.id
    assert json_data["data"]["status"] == "pendiente"


def test_reopen_task_unauthenticated_rejected(client):
    # Web endpoint requires login -> redirect 302 to /login
    web_res = client.post("/tasks/1/reopen", follow_redirects=False)
    assert web_res.status_code == 302
    assert "/login" in web_res.headers["Location"]

    # API endpoint requires login -> 401
    api_res = client.post("/api/tasks/1/reopen")
    assert api_res.status_code == 401


def test_reopen_task_non_completed_fails(auth_client, task_service):
    client, user = auth_client
    t_pending = task_service.create_task(user.id, "Tarea Pendiente no Reabrible")

    web_res = client.post(f"/tasks/{t_pending.id}/reopen")
    assert web_res.status_code == 400

    api_res = client.post(f"/api/tasks/{t_pending.id}/reopen")
    assert api_res.status_code == 400
    assert api_res.get_json()["status"] == "error"


def test_reopen_task_nonexistent_alien_or_deleted_fails(auth_client, user_service, task_service):
    client, user = auth_client

    # 1. Nonexistent task
    assert client.post("/tasks/99999/reopen").status_code == 404
    assert client.post("/api/tasks/99999/reopen").status_code == 404

    # 2. Alien task
    alien_user = user_service.register_user("alien_reopen@example.com", "password123")
    alien_task = task_service.create_task(alien_user.id, "Tarea Alien")
    task_service.update_task_status(alien_task.id, alien_user.id, "en_progreso")
    task_service.update_task_status(alien_task.id, alien_user.id, "completada")

    assert client.post(f"/tasks/{alien_task.id}/reopen").status_code == 404
    assert client.post(f"/api/tasks/{alien_task.id}/reopen").status_code == 404

    # 3. Deleted task
    own_task = task_service.create_task(user.id, "Tarea Borrada no Reabrible")
    task_service.update_task_status(own_task.id, user.id, "en_progreso")
    task_service.update_task_status(own_task.id, user.id, "completada")
    task_service.delete_task(own_task.id, user.id)

    assert client.post(f"/tasks/{own_task.id}/reopen").status_code == 404
    assert client.post(f"/api/tasks/{own_task.id}/reopen").status_code == 404





