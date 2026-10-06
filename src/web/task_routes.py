from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g, abort
)
from src.web.app import get_db
from src.web.auth_routes import login_required
from src.infrastructure.repositories import TaskRepository, AuditLogRepository, CategoryRepository, UserRepository, NotificationRepository
from src.domain.services import TaskService, CategoryService, _NO_CHANGE, CollaborationService
from src.domain.exceptions import ValidationError, NotFoundError, UnauthorizedError, InvalidStateTransitionError, TaskNotAccessibleError, OperationNotPermittedError, ConflictError

task_bp = Blueprint("tasks", __name__)


def get_task_service() -> TaskService:
    session = get_db()
    task_repo = TaskRepository(session)
    audit_repo = AuditLogRepository(session)
    category_repo = CategoryRepository(session)
    return TaskService(task_repo, audit_repo, category_repo=category_repo, session=session)


def get_category_service() -> CategoryService:
    session = get_db()
    repo = CategoryRepository(session)
    return CategoryService(repo, session=session)


def get_collaboration_service() -> CollaborationService:
    session = get_db()
    task_repo = TaskRepository(session)
    user_repo = UserRepository(session)
    audit_repo = AuditLogRepository(session)
    notification_repo = NotificationRepository(session)
    return CollaborationService(task_repo, user_repo, audit_repo, notification_repo, session=session)


@task_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks_view():
    user_id = session["user_id"]
    status_filter = request.args.get("status")
    status_val = status_filter if status_filter else "todas"
    role_filter = request.args.get("role", "all")
    sort = request.args.get("sort")
    if not sort:
        sort = "manual" if role_filter == "owned" else "created_desc"
    category_filter = request.args.get("category_id")
    task_service = get_task_service()
    category_service = get_category_service()
    categories = category_service.list_categories(user_id)

    try:
        tasks = task_service.list_tasks_visible(
            user_id,
            role=role_filter,
            status=status_val,
            sort=sort,
            category_id=category_filter
        )
    except ValidationError as e:
        flash(str(e), "error")
        tasks = task_service.list_tasks_visible(user_id, role="all", status="todas", sort="created_desc")
        status_filter = None
        sort = "created_desc"
        role_filter = "all"
        category_filter = None

    return render_template(
        "tasks/list.html",
        tasks=tasks,
        categories=categories,
        current_filter=status_filter,
        current_sort=sort,
        current_category=category_filter,
        current_role=role_filter,
        user_id=user_id
    )


@task_bp.route("/api/tasks", methods=["GET"])
@login_required
def list_tasks_api():
    user_id = session["user_id"]
    role_filter = request.args.get("role", "all")
    status_filter = request.args.get("status", "todas")
    sort = request.args.get("sort")
    if not sort:
        sort = "manual" if role_filter == "owned" else "created_desc"
    category_filter = request.args.get("category_id")

@task_bp.route("/api/tasks/order", methods=["PATCH"])
@login_required
def update_task_order_api():
    """
    Actualiza el orden manual de las tareas del usuario.
    Espera JSON: {"task_ids": [id1, id2, ...]}
    """
    user_id = session.get("user_id")
    
    data = request.get_json()
    if not data or "task_ids" not in data:
        return jsonify({"status": "error", "error": "El cuerpo debe incluir 'task_ids' como un arreglo."}), 400
        
    task_ids = data["task_ids"]
    if not isinstance(task_ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in task_ids):
        return jsonify({"status": "error", "error": "El arreglo 'task_ids' debe contener solo números enteros."}), 400
        
    if len(task_ids) != len(set(task_ids)):
        return jsonify({"status": "error", "error": "El arreglo no puede contener identificadores duplicados."}), 400
        
    task_service = get_task_service()
    
    try:
        changed_count = task_service.update_task_order(user_id, task_ids)
        return jsonify({"status": "success", "changed": changed_count}), 200
    except ValidationError as e:
        return jsonify({"status": "error", "error": str(e)}), 400
    except OperationNotPermittedError as e:
        return jsonify({"status": "error", "error": str(e)}), 403
    except TaskNotAccessibleError as e:
        return jsonify({"status": "error", "error": str(e)}), 404
    except ConflictError as e:
        return jsonify({"status": "error", "error": str(e)}), 409
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "error": "Error interno al reordenar tareas."}), 500
    task_service = get_task_service()

    try:
        tasks = task_service.list_tasks_visible(
            user_id,
            role=role_filter,
            status=status_filter,
            sort=sort,
            category_id=category_filter
        )
        task_data = [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date,
                "status": t.status,
                "priority": t.priority,
                "category_id": t.category_id,
                "category_name": t.category_name,
                "is_overdue": t.is_overdue,
                "viewer_role": "owner" if t.user_id == user_id else "assignee",
                "owner": {"id": t.user_id, "email": t.owner_email} if t.owner_email else {"id": t.user_id, "email": ""},
                "assignee": {"id": t.assignee_id, "email": t.assignee_email} if t.assignee_id and t.assignee_email else None,
                "permissions": {
                    "can_edit": t.user_id == user_id,
                    "can_delete": t.user_id == user_id,
                    "can_manage_assignment": t.user_id == user_id,
                    "can_change_status": True,
                    "can_reopen": True
                },
                "created_at": t.created_at,
                "updated_at": t.updated_at
            }
            for t in tasks
        ]
        return jsonify({
            "status": "success",
            "success": True,
            "tasks": task_data,
            "data": task_data
        }), 200
    except ValidationError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 400


@task_bp.route("/api/tasks/<int:id>", methods=["GET"])
@login_required
def get_task_api(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        t = task_service.get_task(id, user_id)
        return jsonify({
            "status": "success",
            "success": True,
            "data": {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date,
                "status": t.status,
                "priority": t.priority,
                "category_id": t.category_id,
                "category_name": t.category_name,
                "is_overdue": t.is_overdue,
                "viewer_role": "owner" if t.user_id == user_id else "assignee",
                "owner": {"id": t.user_id, "email": t.owner_email} if t.owner_email else {"id": t.user_id, "email": ""},
                "assignee": {"id": t.assignee_id, "email": t.assignee_email} if t.assignee_id and t.assignee_email else None,
                "created_at": t.created_at,
                "updated_at": t.updated_at
            }
        }), 200
    except NotFoundError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except UnauthorizedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403



@task_bp.route("/tasks/create", methods=["GET"])
@login_required
def create_task_view():
    user_id = session["user_id"]
    category_service = get_category_service()
    categories = category_service.list_categories(user_id)
    return render_template("tasks/create.html", categories=categories)


@task_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    user_id = session["user_id"]
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    title = data.get("title", "") if data else ""
    description = data.get("description", "") if data else ""
    due_date = data.get("due_date", "") if data else ""
    priority = (data.get("priority", "media") if data else "media") or "media"

    category_id_raw = data.get("category_id") if data else None
    category_id = None
    if category_id_raw is not None and category_id_raw != "" and str(category_id_raw).lower() != "none":
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            category_id = None

    task_service = get_task_service()
    try:
        task = task_service.create_task(
            user_id=user_id,
            title=title,
            description=description if description else None,
            due_date=due_date if due_date else None,
            priority=priority,
            category_id=category_id
        )

        if is_json:
            return jsonify({
                "status": "success",
                "success": True,
                "data": {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "due_date": task.due_date,
                    "status": task.status,
                    "priority": task.priority,
                    "category_id": task.category_id,
                    "category_name": task.category_name,
                    "is_overdue": task.is_overdue,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at
                }
            }), 201

        flash("¡Tarea creada exitosamente!", "success")
        return redirect(url_for("tasks.list_tasks_view"))

    except (ValidationError, NotFoundError, UnauthorizedError) as e:
        if is_json:
            status_code = 404 if isinstance(e, NotFoundError) else (403 if isinstance(e, UnauthorizedError) else 400)
            return jsonify({"status": "error", "success": False, "error": str(e)}), status_code
        flash(str(e), "error")
        category_service = get_category_service()
        categories = category_service.list_categories(user_id)
        return render_template(
            "tasks/create.html",
            categories=categories,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            category_id=category_id
        ), 400


@task_bp.route("/tasks/<int:id>", methods=["GET"])
@login_required
def detail_task_view(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        task = task_service.get_task(id, user_id)
        viewer_role = "owner" if task.user_id == user_id else "assignee"
        return render_template("tasks/detail.html", task=task, viewer_role=viewer_role)
    except (NotFoundError, TaskNotAccessibleError):
        abort(404)
    except UnauthorizedError:
        abort(403)

@task_bp.route("/tasks/<int:id>/assignee", methods=["POST"])
@login_required
def update_task_assignee_view(id):
    user_id = session["user_id"]
    assignee_email = request.form.get("assignee_email", "").strip()
    collab_service = get_collaboration_service()
    try:
        if assignee_email:
            collab_service.assign_task(id, user_id, assignee_email)
            flash("Tarea asignada exitosamente.", "success")
        else:
            flash("El correo del asignado es obligatorio.", "error")
        return redirect(url_for("tasks.detail_task_view", id=id))
    except ValidationError as e:
        flash(str(e), "error")
        return redirect(url_for("tasks.detail_task_view", id=id))
    except (NotFoundError, TaskNotAccessibleError):
        abort(404)
    except (UnauthorizedError, OperationNotPermittedError):
        abort(403)
    except ConflictError as e:
        flash(str(e), "error")
        return redirect(url_for("tasks.detail_task_view", id=id))

@task_bp.route("/tasks/<int:id>/assignee/delete", methods=["POST"])
@login_required
def delete_task_assignee_view(id):
    user_id = session["user_id"]
    collab_service = get_collaboration_service()
    try:
        collab_service.unassign_task(id, user_id)
        flash("Asignación removida exitosamente.", "success")
        return redirect(url_for("tasks.detail_task_view", id=id))
    except (NotFoundError, TaskNotAccessibleError):
        abort(404)
    except (UnauthorizedError, OperationNotPermittedError):
        abort(403)
    except ConflictError as e:
        flash(str(e), "error")
        return redirect(url_for("tasks.detail_task_view", id=id))


@task_bp.route("/tasks/<int:id>/edit", methods=["GET"])
@login_required
def edit_task_view(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    category_service = get_category_service()
    try:
        task = task_service.get_task(id, user_id)
        categories = category_service.list_categories(user_id)
        return render_template("tasks/edit.html", task=task, categories=categories)
    except (NotFoundError, UnauthorizedError, TaskNotAccessibleError):
        abort(404)


@task_bp.route("/tasks/<int:id>/edit", methods=["POST"])
@login_required
def update_task_view(id):
    user_id = session["user_id"]
    title = request.form.get("title", "")
    description = request.form.get("description", "")
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "media")
    category_id_raw = request.form.get("category_id")

    category_id = None
    if category_id_raw is not None and category_id_raw != "" and str(category_id_raw).lower() != "none":
        try:
            category_id = int(category_id_raw)
        except (ValueError, TypeError):
            category_id = None

    task_service = get_task_service()
    try:
        task_service.update_task(
            task_id=id,
            user_id=user_id,
            title=title,
            description=description if description else None,
            due_date=due_date if due_date else None,
            priority=priority,
            category_id=category_id
        )
        flash("Tarea actualizada exitosamente.", "success")
        return redirect(url_for("tasks.list_tasks_view"))
    except ValidationError as e:
        flash(str(e), "error")
        task = task_service.get_task(id, user_id)
        category_service = get_category_service()
        categories = category_service.list_categories(user_id)
        return render_template(
            "tasks/edit.html",
            task=task,
            categories=categories,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            category_id=category_id
        ), 400
    except (NotFoundError, UnauthorizedError):
        abort(404)


@task_bp.route("/api/tasks/<int:id>", methods=["PUT"])
@login_required
def update_task_api(id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    title = data.get("title", "")
    description = data.get("description")
    due_date = data.get("due_date")
    priority = data.get("priority")
    category_id = data.get("category_id") if "category_id" in data else _NO_CHANGE

    task_service = get_task_service()
    try:
        updated = task_service.update_task(
            task_id=id,
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            category_id=category_id
        )
        return jsonify({
            "status": "success",
            "success": True,
            "data": {
                "id": updated.id,
                "title": updated.title,
                "description": updated.description,
                "due_date": updated.due_date,
                "status": updated.status,
                "priority": updated.priority,
                "category_id": updated.category_id,
                "category_name": updated.category_name,
                "is_overdue": updated.is_overdue,
                "updated_at": updated.updated_at
            }
        }), 200
    except ValidationError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403


@task_bp.route("/api/tasks/<int:id>/category", methods=["PATCH"])
@login_required
def update_task_category_api(id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    category_id = data.get("category_id")

    task_service = get_task_service()
    try:
        updated = task_service.update_task_category(id, user_id, category_id)
        return jsonify({
            "status": "success",
            "success": True,
            "data": {
                "id": updated.id,
                "category_id": updated.category_id,
                "category_name": updated.category_name,
                "updated_at": updated.updated_at
            }
        }), 200
    except ValidationError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403


@task_bp.route("/api/tasks/<int:id>/priority", methods=["PATCH"])
@login_required
def update_task_priority_api(id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    priority = data.get("priority")

    if not priority:
        return jsonify({"status": "error", "success": False, "error": "El nivel de prioridad es obligatorio"}), 400

    task_service = get_task_service()
    try:
        updated = task_service.update_task_priority(id, user_id, priority)
        return jsonify({
            "status": "success",
            "success": True,
            "task": {
                "id": updated.id,
                "priority": updated.priority,
                "updated_at": updated.updated_at
            },
            "data": {
                "id": updated.id,
                "priority": updated.priority,
                "updated_at": updated.updated_at
            }
        }), 200
    except ValidationError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403


@task_bp.route("/api/tasks/<int:id>/status", methods=["PATCH"])
@login_required
def update_task_status_api(id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    target_status = data.get("status")

    if not target_status:
        return jsonify({"success": False, "error": "El nuevo estado es obligatorio"}), 400

    task_service = get_task_service()
    try:
        updated = task_service.update_task_status(id, user_id, target_status)
        return jsonify({
            "success": True,
            "data": {
                "id": updated.id,
                "status": updated.status,
                "is_overdue": updated.is_overdue,
                "updated_at": updated.updated_at
            }
        }), 200
    except (InvalidStateTransitionError, ValidationError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"success": False, "error": str(e)}), 403


@task_bp.route("/tasks/<int:id>/delete", methods=["POST"])
@login_required
def delete_task_view(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        task_service.delete_task(id, user_id)
        flash("Tarea eliminada exitosamente.", "success")
        return redirect(url_for("tasks.list_tasks_view"))
    except (NotFoundError, UnauthorizedError):
        abort(404)


@task_bp.route("/api/tasks/<int:id>", methods=["DELETE"])
@login_required
def delete_task_api(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        deleted = task_service.delete_task(id, user_id)
        return jsonify({
            "status": "success",
            "message": "Tarea eliminada exitosamente.",
            "data": {
                "id": deleted.id,
                "is_deleted": True
            }
        }), 200
    except (NotFoundError, TaskNotAccessibleError):
        return jsonify({
            "status": "error",
            "message": "Tarea no encontrada o ya eliminada"
        }), 404
    except (UnauthorizedError, OperationNotPermittedError):
        return jsonify({
            "status": "error",
            "message": "No tiene permiso para eliminar la tarea"
        }), 403


@task_bp.route("/tasks/<int:id>/reopen", methods=["POST"])
@login_required
def reopen_task_view(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        task_service.reopen_task(id, user_id)
        flash("Tarea reabierta exitosamente.", "success")
        return redirect(url_for("tasks.list_tasks_view"))
    except InvalidStateTransitionError:
        abort(400)
    except (NotFoundError, UnauthorizedError):
        abort(404)


@task_bp.route("/api/tasks/<int:id>/reopen", methods=["POST"])
@login_required
def reopen_task_api(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        reopened = task_service.reopen_task(id, user_id)
        return jsonify({
            "status": "success",
            "message": "Tarea reabierta exitosamente.",
            "data": {
                "id": reopened.id,
                "status": reopened.status,
                "is_overdue": reopened.is_overdue
            }
        }), 200
    except InvalidStateTransitionError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except (NotFoundError, TaskNotAccessibleError):
        return jsonify({
            "status": "error",
            "message": "Tarea no encontrada o no autorizada"
        }), 404
    except (UnauthorizedError, OperationNotPermittedError):
        return jsonify({
            "status": "error",
            "message": "No tiene permiso para reabrir la tarea"
        }), 403


@task_bp.route("/api/tasks/<int:id>/assignee", methods=["PUT"])
@login_required
def update_task_assignee_api(id):
    user_id = session["user_id"]
    data = request.get_json() or {}
    assignee_email = data.get("assignee_email")

    if not assignee_email:
        return jsonify({"success": False, "error": "El correo del asignado es obligatorio."}), 400

    collab_service = get_collaboration_service()
    try:
        changed, action, assignee = collab_service.assign_task(id, user_id, assignee_email)
        return jsonify({
            "success": True,
            "data": {
                "task_id": id,
                "assignee": {"id": assignee.id, "email": assignee.email} if assignee else None,
                "changed": changed,
                "action": action
            }
        }), 200
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except ConflictError as e:
        return jsonify({"success": False, "error": str(e)}), 409


@task_bp.route("/api/tasks/<int:id>/assignee", methods=["DELETE"])
@login_required
def delete_task_assignee_api(id):
    user_id = session["user_id"]
    collab_service = get_collaboration_service()
    try:
        changed, action, _ = collab_service.unassign_task(id, user_id)
        return jsonify({
            "success": True,
            "data": {
                "task_id": id,
                "assignee": None,
                "changed": changed,
                "action": action
            }
        }), 200
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except TaskNotAccessibleError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except OperationNotPermittedError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except UnauthorizedError as e:
        return jsonify({"success": False, "error": str(e)}), 403
    except ConflictError as e:
        return jsonify({"success": False, "error": str(e)}), 409
