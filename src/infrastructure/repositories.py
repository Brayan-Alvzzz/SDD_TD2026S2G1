from datetime import datetime, timezone
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.orm import Session
from src.domain.models import User, Task, AuditLog
from src.infrastructure.models import UserORM, TaskORM, AuditLogORM


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc).isoformat()
        user_orm = UserORM(
            email=email.strip().lower(),
            password_hash=password_hash,
            created_at=now
        )
        self.session.add(user_orm)
        self.session.flush()
        return User(id=user_orm.id, email=user_orm.email, password_hash=user_orm.password_hash, created_at=user_orm.created_at)

    def get_by_id(self, user_id: int) -> Optional[User]:
        user_orm = self.session.get(UserORM, user_id)
        if user_orm:
            return User(id=user_orm.id, email=user_orm.email, password_hash=user_orm.password_hash, created_at=user_orm.created_at)
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = sa.select(UserORM).where(sa.func.lower(UserORM.email) == email.strip().lower())
        user_orm = self.session.execute(stmt).scalars().first()
        if user_orm:
            return User(id=user_orm.id, email=user_orm.email, password_hash=user_orm.password_hash, created_at=user_orm.created_at)
        return None


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_id: int, title: str, description: Optional[str] = None, due_date: Optional[str] = None, status: str = "pendiente") -> Task:
        now = datetime.now(timezone.utc).isoformat()
        task_orm = TaskORM(
            user_id=user_id,
            title=title.strip(),
            description=description.strip() if description else None,
            due_date=due_date,
            status=status,
            created_at=now,
            updated_at=now
        )
        self.session.add(task_orm)
        self.session.flush()
        return Task(
            id=task_orm.id,
            user_id=task_orm.user_id,
            title=task_orm.title,
            description=task_orm.description,
            due_date=task_orm.due_date,
            status=task_orm.status,
            is_deleted=task_orm.is_deleted,
            deleted_at=task_orm.deleted_at,
            created_at=task_orm.created_at,
            updated_at=task_orm.updated_at
        )

    def get_by_id(self, task_id: int) -> Optional[Task]:
        task_orm = self.session.get(TaskORM, task_id)
        if task_orm:
            return Task(
                id=task_orm.id,
                user_id=task_orm.user_id,
                title=task_orm.title,
                description=task_orm.description,
                due_date=task_orm.due_date,
                status=task_orm.status,
                is_deleted=task_orm.is_deleted,
                deleted_at=task_orm.deleted_at,
                created_at=task_orm.created_at,
                updated_at=task_orm.updated_at
            )
        return None

    def list_by_user(self, user_id: int, status: Optional[str] = None, include_deleted: bool = False) -> List[Task]:
        stmt = sa.select(TaskORM).where(TaskORM.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(TaskORM.is_deleted == False)
        if status:
            stmt = stmt.where(TaskORM.status == status)
        stmt = stmt.order_by(TaskORM.created_at.desc(), TaskORM.id.desc())
        rows = self.session.execute(stmt).scalars().all()
        return [
            Task(
                id=r.id,
                user_id=r.user_id,
                title=r.title,
                description=r.description,
                due_date=r.due_date,
                status=r.status,
                is_deleted=r.is_deleted,
                deleted_at=r.deleted_at,
                created_at=r.created_at,
                updated_at=r.updated_at
            )
            for r in rows
        ]

    def soft_delete(self, task_id: int, user_id: int, deleted_at: str) -> Optional[Task]:
        task_orm = self.session.get(TaskORM, task_id)
        if not task_orm or task_orm.user_id != user_id:
            return None
        task_orm.is_deleted = True
        task_orm.deleted_at = deleted_at
        task_orm.updated_at = deleted_at
        self.session.flush()
        return Task(
            id=task_orm.id,
            user_id=task_orm.user_id,
            title=task_orm.title,
            description=task_orm.description,
            due_date=task_orm.due_date,
            status=task_orm.status,
            is_deleted=task_orm.is_deleted,
            deleted_at=task_orm.deleted_at,
            created_at=task_orm.created_at,
            updated_at=task_orm.updated_at
        )

    def update(self, task: Task) -> Task:
        now = datetime.now(timezone.utc).isoformat()
        task_orm = self.session.get(TaskORM, task.id)
        if task_orm:
            task_orm.title = task.title
            task_orm.description = task.description
            task_orm.due_date = task.due_date
            task_orm.status = task.status
            task_orm.is_deleted = task.is_deleted
            task_orm.deleted_at = task.deleted_at
            task_orm.updated_at = now
            self.session.flush()
        task.updated_at = now
        return task


class AuditLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, task_id: int, actor_id: int, action: str, details: str) -> AuditLog:
        now = datetime.now(timezone.utc).isoformat()
        audit_orm = AuditLogORM(
            task_id=task_id,
            actor_id=actor_id,
            action=action,
            details=details,
            created_at=now
        )
        self.session.add(audit_orm)
        self.session.flush()
        return AuditLog(
            id=audit_orm.id,
            task_id=audit_orm.task_id,
            actor_id=audit_orm.actor_id,
            action=audit_orm.action,
            details=audit_orm.details,
            created_at=audit_orm.created_at
        )

    def list_by_task(self, task_id: int) -> List[AuditLog]:
        stmt = sa.select(AuditLogORM).where(AuditLogORM.task_id == task_id).order_by(AuditLogORM.created_at.asc(), AuditLogORM.id.asc())
        rows = self.session.execute(stmt).scalars().all()
        return [
            AuditLog(
                id=r.id,
                task_id=r.task_id,
                actor_id=r.actor_id,
                action=r.action,
                details=r.details,
                created_at=r.created_at
            )
            for r in rows
        ]
