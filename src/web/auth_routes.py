from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
)
from src.web.app import get_db
from src.infrastructure.repositories import UserRepository
from src.domain.services import UserService
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError

auth_bp = Blueprint("auth", __name__)


def get_user_service() -> UserService:
    session = get_db()
    repo = UserRepository(session)
    return UserService(repo, session=session)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "No autorizado. Inicie sesión para continuar."}), 401
            flash("Debe iniciar sesión para acceder a esta sección.", "warning")
            return redirect(url_for("auth.login_view"))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route("/register", methods=["GET"])
def register_view():
    if "user_id" in session:
        return redirect(url_for("tasks.list_tasks_view"))
    return render_template("auth/register.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    is_json_req = request.is_json
    data = request.get_json() if is_json_req else request.form

    email = data.get("email", "")
    password = data.get("password", "")

    user_service = get_user_service()
    try:
        user = user_service.register_user(email, password)
        session.clear()
        session["user_id"] = user.id
        session["user_email"] = user.email
        session.permanent = True

        if is_json_req:
            return jsonify({
                "success": True,
                "message": "Usuario registrado con éxito",
                "user": {"id": user.id, "email": user.email}
            }), 201

        flash("¡Registro exitoso! Bienvenido a TaskControl.", "success")
        return redirect(url_for("tasks.list_tasks_view"))

    except ValidationError as e:
        if is_json_req:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(str(e), "error")
        return render_template("auth/register.html", email=email), 400

    except ConflictError as e:
        if is_json_req:
            return jsonify({"success": False, "error": str(e)}), 409
        flash(str(e), "error")
        return render_template("auth/register.html", email=email), 409


@auth_bp.route("/login", methods=["GET"])
def login_view():
    if "user_id" in session:
        return redirect(url_for("tasks.list_tasks_view"))
    return render_template("auth/login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    is_json_req = request.is_json
    data = request.get_json() if is_json_req else request.form

    email = data.get("email", "")
    password = data.get("password", "")

    user_service = get_user_service()
    try:
        user = user_service.authenticate_user(email, password)
        session.clear()
        session["user_id"] = user.id
        session["user_email"] = user.email
        session.permanent = True

        if is_json_req:
            return jsonify({
                "success": True,
                "message": "Inicio de sesión exitoso",
                "user": {"id": user.id, "email": user.email}
            }), 200

        flash("Sesión iniciada correctamente.", "success")
        return redirect(url_for("tasks.list_tasks_view"))

    except UnauthorizedError as e:
        if is_json_req:
            return jsonify({"success": False, "error": str(e)}), 401
        flash(str(e), "error")
        return render_template("auth/login.html", email=email), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"success": True, "message": "Sesión cerrada exitosamente"}), 200
    flash("Has cerrado sesión exitosamente.", "info")
    return redirect(url_for("auth.login_view"))
