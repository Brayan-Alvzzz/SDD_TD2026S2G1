"""SQLAlchemy ORM Models for TaskControl.

Increment 1 + Increment 2 models:
- UserORM: users table
- TaskORM: tasks table (with soft delete columns is_deleted, deleted_at)
- AuditLogORM: audit_logs table (expanded CHECK for delete and reopen)
- PasswordResetTokenORM: password_reset_tokens table
"""
import sqlalchemy as sa
from src.infrastructure.database import db


class UserORM(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255, collation="NOCASE"), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.String(35), nullable=False)

    tasks = db.relationship("TaskORM", backref="user", cascade="all, delete-orphan", passive_deletes=True)
    reset_tokens = db.relationship("PasswordResetTokenORM", backref="user", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        db.Index("idx_users_email", "email"),
    )


class CategoryORM(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.String(35), nullable=False)

    user = db.relationship("UserORM", backref=db.backref("categories", cascade="all, delete-orphan", passive_deletes=True))

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_categories_user_name"),
        db.Index("idx_categories_user_id", "user_id"),
    )


class TaskORM(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(1000), nullable=True)
    due_date = db.Column(db.String(30), nullable=True)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pendiente",
        server_default="pendiente",
    )
    priority = db.Column(
        db.String(10),
        nullable=False,
        default="media",
        server_default="media",
    )
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("0"))
    deleted_at = db.Column(db.String(35), nullable=True)
    created_at = db.Column(db.String(35), nullable=False)
    updated_at = db.Column(db.String(35), nullable=False)

    category = db.relationship("CategoryORM", backref=db.backref("tasks", passive_deletes=True))
    audit_logs = db.relationship("AuditLogORM", backref="task", cascade="all, delete-orphan", passive_deletes=True)

    __table_args__ = (
        db.CheckConstraint("status IN ('pendiente', 'en_progreso', 'completada')", name="chk_tasks_status"),
        db.CheckConstraint("priority IN ('alta', 'media', 'baja')", name="chk_tasks_priority"),
        db.Index("idx_tasks_user_id", "user_id"),
        db.Index("idx_tasks_user_status", "user_id", "status"),
        db.Index("idx_tasks_user_created", "user_id", "created_at"),
        db.Index("idx_tasks_user_active", "user_id", "is_deleted", "created_at"),
        db.Index("idx_tasks_user_priority", "user_id", "priority"),
        db.Index("idx_tasks_user_category", "user_id", "category_id"),
    )


class AuditLogORM(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.String(35), nullable=False)

    actor = db.relationship("UserORM", backref="audit_logs")

    __table_args__ = (
        db.CheckConstraint(
            "action IN ('create', 'update', 'status_change', 'delete', 'reopen', 'priority_change', 'category_change')",
            name="chk_audit_logs_action"
        ),
        db.Index("idx_audit_logs_task", "task_id"),
        db.Index("idx_audit_logs_actor", "actor_id"),
    )


class PasswordResetTokenORM(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.String(35), nullable=False)
    used = db.Column(db.Boolean, nullable=False, default=False, server_default=sa.text("0"))
    created_at = db.Column(db.String(35), nullable=False)

    __table_args__ = (
        db.Index("idx_reset_token_hash", "token_hash"),
        db.Index("idx_reset_token_user_pending", "user_id", "used"),
    )
