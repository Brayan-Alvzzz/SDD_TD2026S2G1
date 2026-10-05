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


# ============================================================================
# HU-07: Prioridad de Tareas y Ordenamiento (Integration Tests)
# ============================================================================

def test_create_task_with_priority_web_and_api(auth_client):
    """Creating a task via web form with explicit priority persists and renders badge."""
    client, user = auth_client
    res = client.post("/tasks", data={
        "title": "Tarea Alta Prioridad",
        "description": "Detalles urgentes",
        "priority": "alta",
    }, follow_redirects=True)

    assert res.status_code == 200
    assert "Tarea Alta Prioridad".encode("utf-8") in res.data
    assert "alta".encode("utf-8") in res.data


def test_edit_task_post_updates_priority(auth_client, task_service):
    """POST /tasks/<id>/edit updates task priority correctly."""
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea a Modificar Prioridad", priority="media")

    res = client.post(f"/tasks/{task.id}/edit", data={
        "title": "Tarea con Prioridad Cambiada",
        "priority": "baja",
    }, follow_redirects=True)

    assert res.status_code == 200
    updated = task_service.get_task(task.id, user.id)
    assert updated.priority == "baja"


def test_patch_api_task_priority_success_and_validations(auth_client, task_service):
    """PATCH /api/tasks/<id>/priority updates priority and rejects invalid values."""
    client, user = auth_client
    task = task_service.create_task(user.id, "Tarea API Priority", priority="media")

    # Success case
    patch_res = client.patch(
        f"/api/tasks/{task.id}/priority",
        json={"priority": "alta"}
    )
    assert patch_res.status_code == 200
    data = patch_res.get_json()
    assert data["status"] == "success"
    assert data["task"]["priority"] == "alta"

    # Validation failure: invalid priority value
    invalid_res = client.patch(
        f"/api/tasks/{task.id}/priority",
        json={"priority": "urgente"}
    )
    assert invalid_res.status_code == 400
    assert invalid_res.get_json()["status"] == "error"


def test_patch_api_task_priority_unauthorized_and_alien(auth_client, user_service, task_service, app):
    """PATCH /api/tasks/<id>/priority enforces authentication and ownership."""
    auth_c, owner = auth_client
    task = task_service.create_task(owner.id, "Tarea Privada")

    # 1. Unauthenticated request
    unauth_client = app.test_client()
    unauth_res = unauth_client.patch(f"/api/tasks/{task.id}/priority", json={"priority": "alta"})
    assert unauth_res.status_code in (401, 302)

    # 2. Alien user request
    alien_user = user_service.register_user("alien_priority@example.com", "password123")
    alien_client = app.test_client()
    with alien_client.session_transaction() as sess:
        sess["user_id"] = alien_user.id
        sess["user_email"] = alien_user.email

    alien_res = alien_client.patch(f"/api/tasks/{task.id}/priority", json={"priority": "alta"})
    assert alien_res.status_code in (403, 404)


def test_task_list_sort_by_priority_web_and_api(auth_client, task_service):
    """Task listing supports sort=priority_desc and sort=priority_asc, defaulting to created_desc."""
    client, user = auth_client
    t_baja = task_service.create_task(user.id, "Tarea Nivel Baja", priority="baja")
    t_media = task_service.create_task(user.id, "Tarea Nivel Media", priority="media")
    t_alta = task_service.create_task(user.id, "Tarea Nivel Alta", priority="alta")

    # API - Default sort (created_at DESC)
    default_api = client.get("/api/tasks")
    assert default_api.status_code == 200
    items_default = default_api.get_json()["tasks"]
    assert [t["id"] for t in items_default] == [t_alta.id, t_media.id, t_baja.id]

    # API - Priority DESC (alta -> media -> baja)
    prio_desc_api = client.get("/api/tasks?sort=priority_desc")
    assert prio_desc_api.status_code == 200
    items_desc = prio_desc_api.get_json()["tasks"]
    assert [t["priority"] for t in items_desc] == ["alta", "media", "baja"]
    assert [t["id"] for t in items_desc] == [t_alta.id, t_media.id, t_baja.id]

    # API - Priority ASC (baja -> media -> alta)
    prio_asc_api = client.get("/api/tasks?sort=priority_asc")
    assert prio_asc_api.status_code == 200
    items_asc = prio_asc_api.get_json()["tasks"]
    assert [t["priority"] for t in items_asc] == ["baja", "media", "alta"]
    assert [t["id"] for t in items_asc] == [t_baja.id, t_media.id, t_alta.id]


def test_task_list_sort_by_priority_combined_with_status_filter(auth_client, task_service):
    """Priority sorting combines with status filters without interference."""
    client, user = auth_client
    t1 = task_service.create_task(user.id, "Pendiente Baja", priority="baja")
    t2 = task_service.create_task(user.id, "Pendiente Alta", priority="alta")
    t3 = task_service.create_task(user.id, "En Progreso Alta", priority="alta")
    task_service.update_task_status(t3.id, user.id, "en_progreso")

    res = client.get("/api/tasks?status=pendiente&sort=priority_desc")
    assert res.status_code == 200
    tasks = res.get_json()["tasks"]
    assert len(tasks) == 2
    assert tasks[0]["id"] == t2.id
    assert tasks[0]["priority"] == "alta"
    assert tasks[1]["id"] == t1.id
    assert tasks[1]["priority"] == "baja"


# ==============================================================================
# Phase 5: Indicación de Tareas Vencidas (HU-09) - T027 Integration Tests
# ==============================================================================

def test_api_tasks_contract_includes_is_overdue(auth_client, task_service):
    """GET /api/tasks includes boolean is_overdue field matching date logic."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    t_past = task_service.create_task(user.id, "API Pasada", due_date=yesterday_utc)
    t_today = task_service.create_task(user.id, "API Hoy", due_date=today_utc)
    t_future = task_service.create_task(user.id, "API Futura", due_date=tomorrow_utc)

    res = client.get("/api/tasks")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    tasks_by_id = {t["id"]: t for t in data["tasks"]}
    assert isinstance(tasks_by_id[t_past.id]["is_overdue"], bool)
    assert tasks_by_id[t_past.id]["is_overdue"] is True
    assert tasks_by_id[t_today.id]["is_overdue"] is False
    assert tasks_by_id[t_future.id]["is_overdue"] is False


def test_tasks_list_html_renders_overdue_badge(auth_client, task_service):
    """GET /tasks renders badge-overdue for tasks with past due_date."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    task_service.create_task(user.id, "Tarea Atrasada", due_date=yesterday_utc)

    res = client.get("/tasks")
    assert res.status_code == 200
    assert "badge badge-overdue".encode("utf-8") in res.data
    assert "Vencida".encode("utf-8") in res.data


def test_tasks_list_html_does_not_render_overdue_badge_for_today_or_future(auth_client, task_service):
    """GET /tasks does NOT render overdue badge for tasks due today, future, or without date."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    task_service.create_task(user.id, "Tarea de Hoy", due_date=today_utc)
    task_service.create_task(user.id, "Tarea de Mañana", due_date=tomorrow_utc)
    task_service.create_task(user.id, "Tarea Sin Fecha")

    res = client.get("/tasks")
    assert res.status_code == 200
    assert "badge-overdue".encode("utf-8") not in res.data
    assert "Vencida".encode("utf-8") not in res.data


def test_completed_past_due_task_removes_overdue_badge_in_view_and_api(auth_client, task_service):
    """Completing a past-due task immediately removes the overdue badge and sets is_overdue=False."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    task = task_service.create_task(user.id, "Tarea a Completar", due_date=yesterday_utc)

    # Initially overdue
    res_initial = client.get("/tasks")
    assert "badge-overdue".encode("utf-8") in res_initial.data

    # Complete it via API
    patch_res = client.patch(f"/api/tasks/{task.id}/status", json={"status": "en_progreso"})
    assert patch_res.status_code == 200
    patch_res2 = client.patch(f"/api/tasks/{task.id}/status", json={"status": "completada"})
    assert patch_res2.status_code == 200

    # API check
    api_res = client.get("/api/tasks?status=completada")
    assert api_res.status_code == 200
    completed_task_data = api_res.get_json()["tasks"][0]
    assert completed_task_data["id"] == task.id
    assert completed_task_data["is_overdue"] is False

    # HTML check
    html_res = client.get("/tasks?status=completada")
    assert html_res.status_code == 200
    assert "badge-overdue".encode("utf-8") not in html_res.data


def test_reopened_past_due_task_restores_overdue_badge(auth_client, task_service):
    """Reopening a completed task with a past due_date restores the overdue badge."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    task = task_service.create_task(user.id, "Tarea para Ciclo Completo", due_date=yesterday_utc)

    # Complete it
    client.patch(f"/api/tasks/{task.id}/status", json={"status": "en_progreso"})
    client.patch(f"/api/tasks/{task.id}/status", json={"status": "completada"})

    # Reopen it
    reopen_res = client.post(f"/api/tasks/{task.id}/reopen")
    assert reopen_res.status_code == 200

    # Should be overdue again in API
    api_res = client.get("/api/tasks")
    tasks = api_res.get_json()["tasks"]
    reopened_api = next(t for t in tasks if t["id"] == task.id)
    assert reopened_api["status"] == "pendiente"
    assert reopened_api["is_overdue"] is True

    # Should have badge in HTML
    html_res = client.get("/tasks")
    assert "badge-overdue".encode("utf-8") in html_res.data
    assert "Vencida".encode("utf-8") in html_res.data


# ==============================================================================
# Regression: Edit Form Preloading and Category Assignment Preservation
# ==============================================================================

def test_get_edit_task_view_preloads_all_fields_and_preserves_post_errors(auth_client, task_service, category_service):
    """GET /tasks/<id>/edit preloads current title, description, due_date, priority, category.
    POST failure preserves user-entered values."""
    client, user = auth_client
    cat = category_service.create_category(user.id, "Infraestructura")
    task = task_service.create_task(
        user_id=user.id,
        title="Tarea Prellenada",
        description="Nota descriptiva preexistente",
        due_date="2026-11-20",
        priority="alta",
        category_id=cat.id
    )

    # 1. GET edit form: must preload all fields from existing task
    res = client.get(f"/tasks/{task.id}/edit")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert 'value="Tarea Prellenada"' in html
    assert "Nota descriptiva preexistente" in html
    assert 'value="2026-11-20"' in html
    assert '<option value="alta" selected>' in html
    assert f'<option value="{cat.id}" selected>' in html

    # 2. POST with validation error: must preserve submitted values
    post_err = client.post(f"/tasks/{task.id}/edit", data={
        "title": "   ",  # Invalid empty title
        "description": "Texto editado en borrador",
        "due_date": "2026-12-15",
        "priority": "baja",
        "category_id": str(cat.id)
    }, follow_redirects=True)
    assert post_err.status_code == 400
    html_err = post_err.data.decode("utf-8")
    assert "obligatorio" in html_err
    assert "Texto editado en borrador" in html_err
    assert 'value="2026-12-15"' in html_err
    assert '<option value="baja" selected>' in html_err


def test_assign_category_preserves_title_description_and_due_date(auth_client, task_service, category_service):
    """Assigning or changing a category does not wipe title, description, or due_date."""
    client, user = auth_client
    cat = category_service.create_category(user.id, "Desarrollo")
    task = task_service.create_task(
        user_id=user.id,
        title="Tarea No Borrable",
        description="Esta descripción debe persistir intacta",
        due_date="2026-11-18",
        priority="alta"
    )

    # 1. Assign category via API PATCH
    patch_res = client.patch(f"/api/tasks/{task.id}/category", json={"category_id": cat.id})
    assert patch_res.status_code == 200
    fetched_api = task_service.get_task(task.id, user.id)
    assert fetched_api.category_id == cat.id
    assert fetched_api.title == "Tarea No Borrable"
    assert fetched_api.description == "Esta descripción debe persistir intacta"
    assert fetched_api.due_date == "2026-11-18"
    assert fetched_api.priority == "alta"

    # 2. Assign category via Web Edit Form submitting existing preloaded data
    cat2 = category_service.create_category(user.id, "Testing")
    post_res = client.post(f"/tasks/{task.id}/edit", data={
        "title": fetched_api.title,
        "description": fetched_api.description,
        "due_date": fetched_api.due_date,
        "priority": fetched_api.priority,
        "category_id": str(cat2.id)
    }, follow_redirects=True)
    assert post_res.status_code == 200

    fetched_web = task_service.get_task(task.id, user.id)
    assert fetched_web.category_id == cat2.id
    assert fetched_web.title == "Tarea No Borrable"
    assert fetched_web.description == "Esta descripción debe persistir intacta"
    assert fetched_web.due_date == "2026-11-18"
    assert fetched_web.priority == "alta"


def test_task_status_and_reopen_api_contract_for_dynamic_overdue_ui(auth_client, task_service):
    """PATCH /api/tasks/<id>/status and POST /api/tasks/<id>/reopen return is_overdue
    to dynamically toggle the overdue badge in client-side optimistic UI."""
    from datetime import datetime, timedelta, timezone
    client, user = auth_client

    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_utc = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    task_past = task_service.create_task(user.id, "Past Task", due_date=yesterday_utc)
    task_future = task_service.create_task(user.id, "Future Task", due_date=tomorrow_utc)

    # Verify HTML includes target IDs for dynamic badge manipulation
    html_res = client.get("/tasks")
    assert f'id="task-due-{task_past.id}"' in html_res.data.decode("utf-8")
    assert f'id="task-overdue-{task_past.id}"' in html_res.data.decode("utf-8")

    # 1. Advance past task to 'en_progreso' -> still overdue
    res_prog = client.patch(f"/api/tasks/{task_past.id}/status", json={"status": "en_progreso"})
    assert res_prog.status_code == 200
    assert res_prog.get_json()["data"]["status"] == "en_progreso"
    assert res_prog.get_json()["data"]["is_overdue"] is True

    # 2. Advance past task to 'completada' -> immediately NOT overdue
    res_comp = client.patch(f"/api/tasks/{task_past.id}/status", json={"status": "completada"})
    assert res_comp.status_code == 200
    assert res_comp.get_json()["data"]["status"] == "completada"
    assert res_comp.get_json()["data"]["is_overdue"] is False

    # 3. Reopen past task -> immediately overdue again
    res_reopen = client.post(f"/api/tasks/{task_past.id}/reopen")
    assert res_reopen.status_code == 200
    assert res_reopen.get_json()["data"]["status"] == "pendiente"
    assert res_reopen.get_json()["data"]["is_overdue"] is True

    # 4. Check future task: completing and reopening never sets is_overdue
    client.patch(f"/api/tasks/{task_future.id}/status", json={"status": "en_progreso"})
    res_fut_comp = client.patch(f"/api/tasks/{task_future.id}/status", json={"status": "completada"})
    assert res_fut_comp.get_json()["data"]["is_overdue"] is False

    res_fut_reopen = client.post(f"/api/tasks/{task_future.id}/reopen")
    assert res_fut_reopen.get_json()["data"]["is_overdue"] is False









