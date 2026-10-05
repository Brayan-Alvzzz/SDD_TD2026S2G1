from datetime import datetime, timezone
from typing import Optional, List, Union
import sqlalchemy as sa
from sqlalchemy.orm import Session
from src.domain.models import User, Task, AuditLog, PasswordResetToken, Category
from src.infrastructure.models import UserORM, TaskORM, AuditLogORM, PasswordResetTokenORM, CategoryORM


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

    def update_password(self, user_id: int, password_hash: str) -> None:
        user_orm = self.session.get(UserORM, user_id)
        if user_orm:
            user_orm.password_hash = password_hash
            self.session.flush()


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def _to_domain(self, r: TaskORM) -> Task:
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_overdue = False
        if not r.is_deleted and r.status != "completada" and r.due_date and r.due_date.strip():
            is_overdue = r.due_date.strip() < today_utc

        category_name = None
        if getattr(r, "category", None) is not None:
            category_name = r.category.name
        elif r.category_id is not None:
            cat_orm = self.session.get(CategoryORM, r.category_id)
            if cat_orm:
                category_name = cat_orm.name

        return Task(
            id=r.id,
            user_id=r.user_id,
            title=r.title,
            description=r.description,
            due_date=r.due_date,
            status=r.status,
            priority=r.priority if r.priority else "media",
            category_id=r.category_id,
            category_name=category_name,
            is_overdue=is_overdue,
            is_deleted=r.is_deleted,
            deleted_at=r.deleted_at,
            created_at=r.created_at,
            updated_at=r.updated_at
        )

    def create(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        status: str = "pendiente",
        priority: str = "media",
        category_id: Optional[int] = None
    ) -> Task:
        now = datetime.now(timezone.utc).isoformat()
        task_orm = TaskORM(
            user_id=user_id,
            title=title.strip(),
            description=description.strip() if description else None,
            due_date=due_date,
            status=status,
            priority=priority or "media",
            category_id=category_id,
            created_at=now,
            updated_at=now
        )
        self.session.add(task_orm)
        self.session.flush()
        return self._to_domain(task_orm)

    def get_by_id(self, task_id: int) -> Optional[Task]:
        task_orm = self.session.get(TaskORM, task_id)
        if task_orm:
            return self._to_domain(task_orm)
        return None

    def list_by_user(
        self,
        user_id: int,
        status: Optional[str] = None,
        include_deleted: bool = False,
        sort: str = "created_desc",
        category_id: Optional[Union[int, str]] = None
    ) -> List[Task]:
        stmt = sa.select(TaskORM).where(TaskORM.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(TaskORM.is_deleted == False)
        if status:
            stmt = stmt.where(TaskORM.status == status)

        if category_id is not None and category_id != "":
            if str(category_id).lower() == "none":
                stmt = stmt.where(TaskORM.category_id.is_(None))
            else:
                try:
                    stmt = stmt.where(TaskORM.category_id == int(category_id))
                except (ValueError, TypeError):
                    pass

        if sort == "priority_desc":
            priority_order = sa.case(
                (TaskORM.priority == 'alta', 1),
                (TaskORM.priority == 'media', 2),
                (TaskORM.priority == 'baja', 3),
                else_=4
            )
            stmt = stmt.order_by(priority_order.asc(), TaskORM.created_at.desc(), TaskORM.id.desc())
        elif sort == "priority_asc":
            priority_order = sa.case(
                (TaskORM.priority == 'baja', 1),
                (TaskORM.priority == 'media', 2),
                (TaskORM.priority == 'alta', 3),
                else_=4
            )
            stmt = stmt.order_by(priority_order.asc(), TaskORM.created_at.desc(), TaskORM.id.desc())
        else:
            stmt = stmt.order_by(TaskORM.created_at.desc(), TaskORM.id.desc())

        rows = self.session.execute(stmt).scalars().all()
        return [self._to_domain(r) for r in rows]

    def soft_delete(self, task_id: int, user_id: int, deleted_at: str) -> Optional[Task]:
        task_orm = self.session.get(TaskORM, task_id)
        if not task_orm or task_orm.user_id != user_id:
            return None
        task_orm.is_deleted = True
        task_orm.deleted_at = deleted_at
        task_orm.updated_at = deleted_at
        self.session.flush()
        return self._to_domain(task_orm)

    def update(self, task: Task) -> Task:
        now = datetime.now(timezone.utc).isoformat()
        task_orm = self.session.get(TaskORM, task.id)
        if task_orm:
            task_orm.title = task.title
            task_orm.description = task.description
            task_orm.due_date = task.due_date
            task_orm.status = task.status
            task_orm.priority = task.priority or "media"
            task_orm.category_id = task.category_id
            task_orm.is_deleted = task.is_deleted
            task_orm.deleted_at = task.deleted_at
            task_orm.updated_at = now
            self.session.flush()
            return self._to_domain(task_orm)
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


class PasswordResetTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_token(self, user_id: int, token_hash: str, expires_at: str) -> PasswordResetToken:
        now = datetime.now(timezone.utc).isoformat()
        token_orm = PasswordResetTokenORM(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
            created_at=now
        )
        self.session.add(token_orm)
        self.session.flush()
        return PasswordResetToken(
            id=token_orm.id,
            user_id=token_orm.user_id,
            token_hash=token_orm.token_hash,
            expires_at=token_orm.expires_at,
            used=token_orm.used,
            created_at=token_orm.created_at
        )

    def find_active_by_hash(self, token_hash: str) -> Optional[PasswordResetToken]:
        stmt = sa.select(PasswordResetTokenORM).where(
            PasswordResetTokenORM.token_hash == token_hash,
            PasswordResetTokenORM.used == False
        )
        token_orm = self.session.execute(stmt).scalars().first()
        if token_orm:
            return PasswordResetToken(
                id=token_orm.id,
                user_id=token_orm.user_id,
                token_hash=token_orm.token_hash,
                expires_at=token_orm.expires_at,
                used=token_orm.used,
                created_at=token_orm.created_at
            )
        return None

    def mark_as_used(self, token_id: int) -> None:
        token_orm = self.session.get(PasswordResetTokenORM, token_id)
        if token_orm:
            token_orm.used = True
            self.session.flush()

    def revoke_all_for_user(self, user_id: int) -> None:
        stmt = (
            sa.update(PasswordResetTokenORM)
            .where(
                PasswordResetTokenORM.user_id == user_id,
                PasswordResetTokenORM.used == False
            )
            .values(used=True)
        )
        self.session.execute(stmt)
        self.session.flush()


class CategoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_id: int, name: str) -> Category:
        now = datetime.now(timezone.utc).isoformat()
        clean_name = name.strip()
        cat_orm = CategoryORM(
            user_id=user_id,
            name=clean_name,
            created_at=now
        )
        self.session.add(cat_orm)
        self.session.flush()
        return Category(
            id=cat_orm.id,
            user_id=cat_orm.user_id,
            name=cat_orm.name,
            created_at=cat_orm.created_at,
            task_count=0
        )

    def list_by_user(self, user_id: int) -> List[Category]:
        stmt = (
            sa.select(
                CategoryORM,
                sa.func.count(sa.case((TaskORM.is_deleted == False, TaskORM.id), else_=None)).label("task_count")
            )
            .outerjoin(TaskORM, TaskORM.category_id == CategoryORM.id)
            .where(CategoryORM.user_id == user_id)
            .group_by(CategoryORM.id)
            .order_by(CategoryORM.created_at.asc(), CategoryORM.id.asc())
        )
        rows = self.session.execute(stmt).all()
        return [
            Category(
                id=cat_orm.id,
                user_id=cat_orm.user_id,
                name=cat_orm.name,
                created_at=cat_orm.created_at,
                task_count=int(cnt or 0)
            )
            for cat_orm, cnt in rows
        ]

    def get_by_id(self, category_id: int) -> Optional[Category]:
        cat_orm = self.session.get(CategoryORM, category_id)
        if cat_orm:
            return Category(
                id=cat_orm.id,
                user_id=cat_orm.user_id,
                name=cat_orm.name,
                created_at=cat_orm.created_at
            )
        return None

    def get_by_user_and_name(self, user_id: int, name: str) -> Optional[Category]:
        clean_name = name.strip()
        stmt = sa.select(CategoryORM).where(
            CategoryORM.user_id == user_id,
            sa.func.lower(CategoryORM.name) == sa.func.lower(clean_name)
        )
        cat_orm = self.session.execute(stmt).scalars().first()
        if cat_orm:
            return Category(
                id=cat_orm.id,
                user_id=cat_orm.user_id,
                name=cat_orm.name,
                created_at=cat_orm.created_at
            )
        return None

    def delete(self, category_id: int) -> bool:
        cat_orm = self.session.get(CategoryORM, category_id)
        if not cat_orm:
            return False
        self.session.delete(cat_orm)
        self.session.flush()
        self.session.expire_all()
        return True



