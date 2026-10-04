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


