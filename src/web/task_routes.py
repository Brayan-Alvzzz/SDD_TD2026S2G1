from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, g, abort
)
from src.web.app import get_db
from src.web.auth_routes import login_required
from src.infrastructure.repositories import TaskRepository, AuditLogRepository
from src.domain.services import TaskService
from src.domain.exceptions import ValidationError, NotFoundError, UnauthorizedError, InvalidStateTransitionError

task_bp = Blueprint("tasks", __name__)


def get_task_service() -> TaskService:
    session = get_db()
    task_repo = TaskRepository(session)
    audit_repo = AuditLogRepository(session)
    return TaskService(task_repo, audit_repo, session=session)


@task_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks_view():
    user_id = session["user_id"]
    status_filter = request.args.get("status")
    task_service = get_task_service()

    try:
        tasks = task_service.list_tasks(user_id, status_filter)
    except ValidationError as e:
        flash(str(e), "error")
        tasks = task_service.list_tasks(user_id)
        status_filter = None

    return render_template("tasks/list.html", tasks=tasks, current_filter=status_filter)


@task_bp.route("/api/tasks", methods=["GET"])
@login_required
def list_tasks_api():
    user_id = session["user_id"]
    status_filter = request.args.get("status")
    task_service = get_task_service()

    try:
        tasks = task_service.list_tasks(user_id, status_filter)
        return jsonify({
            "success": True,
            "data": [
                {
                    "id": t.id,
                    "title": t.title,
                    "description": t.description,
                    "due_date": t.due_date,
                    "status": t.status,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at
                }
                for t in tasks
            ]
        }), 200
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@task_bp.route("/tasks/create", methods=["GET"])
@login_required
def create_task_view():
    return render_template("tasks/create.html")


@task_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    user_id = session["user_id"]
    is_json = request.is_json
    data = request.get_json() if is_json else request.form

    title = data.get("title", "")
    description = data.get("description", "")
    due_date = data.get("due_date", "")

    task_service = get_task_service()
    try:
        task = task_service.create_task(
            user_id=user_id,
            title=title,
            description=description if description else None,
            due_date=due_date if due_date else None
        )

        if is_json:
            return jsonify({
                "success": True,
                "data": {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "due_date": task.due_date,
                    "status": task.status,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at
                }
            }), 201

        flash("¡Tarea creada exitosamente!", "success")
        return redirect(url_for("tasks.list_tasks_view"))

    except ValidationError as e:
        if is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(str(e), "error")
        return render_template("tasks/create.html", title=title, description=description, due_date=due_date), 400


@task_bp.route("/tasks/<int:id>/edit", methods=["GET"])
@login_required
def edit_task_view(id):
    user_id = session["user_id"]
    task_service = get_task_service()
    try:
        task = task_service.get_task(id, user_id)
        return render_template("tasks/edit.html", task=task)
    except (NotFoundError, UnauthorizedError):
        abort(404)


@task_bp.route("/tasks/<int:id>/edit", methods=["POST"])
@login_required
def update_task_view(id):
    user_id = session["user_id"]
    title = request.form.get("title", "")
    description = request.form.get("description", "")
    due_date = request.form.get("due_date", "")

    task_service = get_task_service()
    try:
        task_service.update_task(
            task_id=id,
            user_id=user_id,
            title=title,
            description=description if description else None,
            due_date=due_date if due_date else None
        )
        flash("Tarea actualizada exitosamente.", "success")
        return redirect(url_for("tasks.list_tasks_view"))
    except ValidationError as e:
        flash(str(e), "error")
        task = task_service.get_task(id, user_id)
        return render_template("tasks/edit.html", task=task, title=title, description=description, due_date=due_date), 400
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

    task_service = get_task_service()
    try:
        updated = task_service.update_task(
            task_id=id,
            user_id=user_id,
            title=title,
            description=description,
            due_date=due_date
        )
        return jsonify({
            "success": True,
            "data": {
                "id": updated.id,
                "title": updated.title,
                "description": updated.description,
                "due_date": updated.due_date,
                "status": updated.status,
                "updated_at": updated.updated_at
            }
        }), 200
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except UnauthorizedError as e:
        return jsonify({"success": False, "error": str(e)}), 403


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
                "updated_at": updated.updated_at
            }
        }), 200
    except (InvalidStateTransitionError, ValidationError) as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
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
    except (NotFoundError, UnauthorizedError):
        return jsonify({
            "status": "error",
            "message": "Tarea no encontrada o ya eliminada"
        }), 404

