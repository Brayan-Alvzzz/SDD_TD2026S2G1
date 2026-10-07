from datetime import timedelta
import os
from flask import Flask, g, redirect, url_for, session, current_app, request, jsonify
from flask_wtf.csrf import CSRFProtect, CSRFError
from src.infrastructure.database import get_db_connection, init_db_schema


def get_db():
    """Retrieve the active SQLAlchemy session for the current request context."""
    from src.infrastructure.database import db
    return db.session


def create_app(test_config=None) -> Flask:
    """Application factory for TaskControl."""
    app = Flask(__name__, instance_relative_config=True)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-taskcontrol-secret-key-change-in-prod"),
        DATABASE_PATH=os.environ.get("DATABASE_PATH", "taskcontrol.db"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        ENABLE_CONSOLE_PASSWORD_RESET=os.environ.get("ENABLE_CONSOLE_PASSWORD_RESET", "false").lower() in ("true", "1", "yes"),
    )

    if test_config is not None:
        app.config.update(test_config)

    # Resolve DATABASE_PATH to absolute SQLite URI for SQLAlchemy
    db_path = app.config.get("DATABASE_PATH", "taskcontrol.db")
    if db_path == ":memory:":
        abs_db_path = ":memory:"
        uri = "sqlite:///:memory:"
    else:
        abs_db_path = os.path.abspath(db_path)
        uri = f"sqlite:///{abs_db_path.replace(os.sep, '/')}"

    app.config.setdefault("SQLALCHEMY_DATABASE_URI", uri)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # Startup diagnostic log displaying exact resolved database file path
    print(f"[DB RESOLUTION] Flask opening database file: {abs_db_path}")

    # Initialize SQLAlchemy & Flask-Migrate extensions
    from src.infrastructure.database import db, migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize CSRF Protection
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Import models so Alembic / SQLAlchemy metadata discovers them
    import src.infrastructure.models  # noqa: F401

    @app.teardown_appcontext
    def close_db(error=None):
        raw_db = g.pop("db", None)
        if raw_db is not None and hasattr(raw_db, "close"):
            raw_db.close()

    # Context processor for templates
    @app.context_processor
    def inject_user():
        user_id = session.get("user_id")
        unread_count = 0
        if user_id:
            try:
                from src.infrastructure.database import db
                from src.infrastructure.repositories import NotificationRepository
                from src.domain.services import NotificationService
                db_session = db.session
                notif_repo = NotificationRepository(db_session)
                service = NotificationService(notif_repo, db_session)
                unread_count = service.count_unread(user_id)
            except Exception:
                pass

        return {
            "current_user_id": user_id,
            "current_user_email": session.get("user_email"),
            "unread_count": unread_count
        }

    # Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "success": False, "error": f"CSRF: {e.description}"}), 400
        return f"Error 400: CSRF: {e.description}", 400

    # Register Blueprints
    from src.web.auth_routes import auth_bp
    from src.web.task_routes import task_bp
    from src.web.category_routes import category_bp
    from src.web.notification_routes import notification_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(task_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(notification_bp)

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("tasks.list_tasks_view"))
        return redirect(url_for("auth.login_view"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
