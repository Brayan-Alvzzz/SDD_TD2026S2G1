from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort
)
from src.web.app import get_db
from src.web.auth_routes import login_required
from src.infrastructure.repositories import CategoryRepository
from src.domain.services import CategoryService
from src.domain.exceptions import ValidationError, ConflictError, NotFoundError, UnauthorizedError

category_bp = Blueprint("categories", __name__)


def get_category_service() -> CategoryService:
    session = get_db()
    repo = CategoryRepository(session)
    return CategoryService(repo, session=session)


@category_bp.route("/categories", methods=["GET"])
@login_required
def list_categories_view():
    user_id = session["user_id"]
    service = get_category_service()
    categories = service.list_categories(user_id)
    return render_template("categories/list.html", categories=categories)


@category_bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    user_id = session["user_id"]
    is_json = request.is_json
    data = request.get_json() if is_json else request.form
    name = data.get("name", "") if data else ""

    service = get_category_service()
    try:
        cat = service.create_category(user_id=user_id, name=name)
        if is_json:
            return jsonify({
                "status": "success",
                "success": True,
                "data": {
                    "id": cat.id,
                    "name": cat.name,
                    "task_count": cat.task_count,
                    "created_at": cat.created_at
                }
            }), 201

        flash("¡Categoría creada exitosamente!", "success")
        return redirect(url_for("categories.list_categories_view"))

    except ValidationError as e:
        if is_json:
            return jsonify({"status": "error", "success": False, "error": str(e)}), 400
        flash(str(e), "error")
        categories = service.list_categories(user_id)
        return render_template("categories/list.html", categories=categories, name=name), 400

    except ConflictError as e:
        if is_json:
            return jsonify({"status": "error", "success": False, "error": str(e)}), 409
        flash(str(e), "error")
        categories = service.list_categories(user_id)
        return render_template("categories/list.html", categories=categories, name=name), 400


@category_bp.route("/api/categories", methods=["GET"])
@login_required
def list_categories_api():
    user_id = session["user_id"]
    service = get_category_service()
    categories = service.list_categories(user_id)
    return jsonify({
        "status": "success",
        "success": True,
        "data": [
            {
                "id": c.id,
                "name": c.name,
                "task_count": c.task_count,
                "created_at": c.created_at
            }
            for c in categories
        ]
    }), 200


@category_bp.route("/api/categories", methods=["POST"])
@login_required
def create_category_api():
    return create_category()


@category_bp.route("/categories/<int:id>/delete", methods=["POST"])
@login_required
def delete_category_view(id):
    user_id = session["user_id"]
    service = get_category_service()
    try:
        service.delete_category(category_id=id, user_id=user_id)
        flash("Categoría eliminada exitosamente.", "success")
        return redirect(url_for("categories.list_categories_view"))
    except (NotFoundError, UnauthorizedError):
        abort(404)


@category_bp.route("/api/categories/<int:id>", methods=["DELETE"])
@login_required
def delete_category_api(id):
    user_id = session["user_id"]
    service = get_category_service()
    try:
        service.delete_category(category_id=id, user_id=user_id)
        return jsonify({
            "status": "success",
            "success": True,
            "message": "Categoría eliminada exitosamente.",
            "data": {
                "id": id
            }
        }), 200
    except NotFoundError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 404
    except UnauthorizedError as e:
        return jsonify({"status": "error", "success": False, "error": str(e)}), 403
