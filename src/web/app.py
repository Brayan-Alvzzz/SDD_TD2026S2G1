from datetime import timedelta
import os
from flask import Flask, g, redirect, url_for, session, current_app
from src.infrastructure.database import get_db_connection, init_db_schema


def get_db():
    """Retrieve or initialize the active database connection for the current request context."""
    if "db" not in g:
        if current_app.config.get("DATABASE_CONN"):
            g.db = current_app.config["DATABASE_CONN"]
        else:
            db_path = current_app.config.get("DATABASE_PATH", "taskcontrol.db")
            g.db = get_db_connection(db_path)
            init_db_schema(g.db)
    return g.db


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

    # Import models so Alembic / SQLAlchemy metadata discovers them
    import src.infrastructure.models  # noqa: F401

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None and not app.config.get("DATABASE_CONN"):
            db.close()

    # Context processor for templates
    @app.context_processor
    def inject_user():
        return {
            "current_user_id": session.get("user_id"),
            "current_user_email": session.get("user_email")
        }

    # Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # Register Blueprints
    from src.web.auth_routes import auth_bp
    from src.web.task_routes import task_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(task_bp)

    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("tasks.list_tasks_view"))
        return redirect(url_for("auth.login_view"))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
