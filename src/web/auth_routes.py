import hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
)
from src.web.app import get_db
from src.infrastructure.repositories import UserRepository, PasswordResetTokenRepository
from src.infrastructure.notifications import ConsoleNotificationService
from src.domain.services import UserService
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError

auth_bp = Blueprint("auth", __name__)


def get_user_service() -> UserService:
    from flask import current_app, has_app_context
    session = get_db()
    repo = UserRepository(session)
    token_repo = PasswordResetTokenRepository(session)
    console_enabled = current_app.config.get("ENABLE_CONSOLE_PASSWORD_RESET", False) if has_app_context() else False
    notification_service = ConsoleNotificationService(enabled=console_enabled) if console_enabled else None
    return UserService(repo, token_repo=token_repo, notification_service=notification_service, session=session)




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


@auth_bp.route("/forgot-password", methods=["GET"])
def forgot_password_view():
    if "user_id" in session:
        return redirect(url_for("tasks.list_tasks_view"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    is_json_req = request.is_json
    data = request.get_json() if is_json_req else request.form
    email = (data.get("email") or "").strip()

    user_service = get_user_service()
    neutral_message = (
        "Si la dirección de correo electrónico está registrada en el sistema, "
        "se ha enviado un enlace para restablecer la contraseña."
    )

    try:
        user_service.request_password_reset(email, base_url=request.host_url.rstrip("/"))
        if is_json_req:
            return jsonify({"status": "success", "message": neutral_message}), 200
        flash(neutral_message, "info")
        return render_template("auth/forgot_password.html"), 200
    except ValidationError as e:
        if is_json_req:
            return jsonify({"status": "error", "message": str(e)}), 400
        flash(str(e), "error")
        return render_template("auth/forgot_password.html", email=email), 400


@auth_bp.route("/reset-password/<token>", methods=["GET"])
def reset_password_view(token):
    if "user_id" in session:
        return redirect(url_for("tasks.list_tasks_view"))

    user_service = get_user_service()
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    token_obj = user_service.token_repo.find_active_by_hash(token_hash) if user_service.token_repo else None

    if not token_obj:
        flash("El enlace de restablecimiento es inválido o ha expirado.", "error")
        return redirect(url_for("auth.login_view"))

    try:
        token_expires = datetime.fromisoformat(token_obj.expires_at)
        if token_expires.tzinfo is None:
            token_expires = token_expires.replace(tzinfo=timezone.utc)
        if token_expires < datetime.now(timezone.utc):
            flash("El enlace de restablecimiento es inválido o ha expirado.", "error")
            return redirect(url_for("auth.login_view"))
    except Exception:
        flash("El enlace de restablecimiento es inválido o ha expirado.", "error")
        return redirect(url_for("auth.login_view"))

    return render_template("auth/reset_password.html", token=token)


@auth_bp.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    is_json_req = request.is_json
    data = request.get_json() if is_json_req else request.form

    password = data.get("password", "")
    password_confirm = data.get("password_confirm", "")

    user_service = get_user_service()
    try:
        user_service.reset_password(token, password, password_confirm)
        success_message = "Contraseña actualizada exitosamente. Ya puede iniciar sesión."
        if is_json_req:
            return jsonify({"status": "success", "message": success_message}), 200
        flash(success_message, "success")
        return redirect(url_for("auth.login_view"))
    except ValidationError as e:
        if is_json_req:
            return jsonify({"status": "error", "message": str(e)}), 400
        flash(str(e), "error")
        if "inválido" in str(e).lower() or "expirado" in str(e).lower():
            return redirect(url_for("auth.login_view"))
        return render_template("auth/reset_password.html", token=token), 400

