from datetime import datetime, timezone
import re
import json
from typing import Optional, List
from src.domain.models import User, Task, AuditLog
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError, NotFoundError
from src.domain.state_machine import TaskStateMachine
from src.infrastructure.security import hash_password, verify_password
from src.infrastructure.repositories import UserRepository, TaskRepository, AuditLogRepository

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserService:
    def __init__(self, user_repo: UserRepository, session=None):
        self.user_repo = user_repo
        self.session = session or getattr(user_repo, "session", None)

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def register_user(self, email: str, password: str) -> User:
        if not email or not EMAIL_REGEX.match(email.strip()):
            raise ValidationError("Debe proporcionar una dirección de correo electrónico válida.")

        if not password or len(password) < 8 or not password.strip():
            raise ValidationError("La contraseña debe tener al menos 8 caracteres.")

        normalized_email = email.strip().lower()
        existing = self.user_repo.get_by_email(normalized_email)
        if existing:
            raise ConflictError("El correo electrónico ya se encuentra registrado.")

        pwd_hash = hash_password(password)
        try:
            user = self.user_repo.create(normalized_email, pwd_hash)
            self._commit()
            return user
        except Exception:
            self._rollback()
            raise

    def authenticate_user(self, email: str, password: str) -> User:
        if not email or not password:
            raise UnauthorizedError("Credenciales incorrectas.")

        user = self.user_repo.get_by_email(email.strip().lower())
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Credenciales incorrectas.")

        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.user_repo.get_by_id(user_id)


class TaskService:
    def __init__(self, task_repo: TaskRepository, audit_repo: AuditLogRepository, session=None):
        self.task_repo = task_repo
        self.audit_repo = audit_repo
        self.session = session or getattr(task_repo, "session", None) or getattr(audit_repo, "session", None)

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def create_task(self, user_id: int, title: str, description: Optional[str] = None, due_date: Optional[str] = None) -> Task:
        if not title or not title.strip():
            raise ValidationError("El título de la tarea es obligatorio y no puede estar vacío.")

        cleaned_title = title.strip()
        if len(cleaned_title) > 150:
            raise ValidationError("El título de la tarea no puede exceder los 150 caracteres.")

        cleaned_description = description.strip() if description else None
        if cleaned_description and len(cleaned_description) > 1000:
            raise ValidationError("La descripción de la tarea no puede exceder los 1,000 caracteres.")

        try:
            task = self.task_repo.create(
                user_id=user_id,
                title=cleaned_title,
                description=cleaned_description,
                due_date=due_date.strip() if due_date else None,
                status="pendiente"
            )

            # Audit log creation event
            audit_details = json.dumps({"title": task.title, "status": task.status})
            self.audit_repo.create(
                task_id=task.id,
                actor_id=user_id,
                action="create",
                details=audit_details
            )

            self._commit()
            return task
        except Exception:
            self._rollback()
            raise

    def list_tasks(self, user_id: int, status: Optional[str] = None) -> List[Task]:
        if status and status not in ("pendiente", "en_progreso", "completada"):
            raise ValidationError(f"Filtro de estado inválido: '{status}'.")
        return self.task_repo.list_by_user(user_id, status)

    def get_task(self, task_id: int, user_id: int, include_deleted: bool = False) -> Task:
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Tarea no encontrada.")
        if task.user_id != user_id:
            raise UnauthorizedError("No tiene permiso para acceder a esta tarea.")
        if not include_deleted and task.is_deleted:
            raise NotFoundError("Tarea no encontrada.")
        return task

    def delete_task(self, task_id: int, user_id: int) -> Task:
        task = self.get_task(task_id, user_id, include_deleted=True)
        if task.is_deleted:
            raise NotFoundError("La tarea ya fue eliminada o no se encuentra disponible.")

        now = datetime.now(timezone.utc).isoformat()
        try:
            deleted = self.task_repo.soft_delete(task_id=task.id, user_id=user_id, deleted_at=now)

            # Audit log delete event
            audit_details = json.dumps({"title": task.title, "status": task.status})
            self.audit_repo.create(
                task_id=task.id,
                actor_id=user_id,
                action="delete",
                details=audit_details
            )

            self._commit()
            return deleted
        except Exception:
            self._rollback()
            raise

    def update_task_status(self, task_id: int, user_id: int, target_status: str) -> Task:
        task = self.get_task(task_id, user_id)
        if task.is_deleted:
            raise ValidationError("No se puede cambiar el estado de una tarea eliminada.")
        old_status = task.status

        TaskStateMachine.validate_transition(old_status, target_status)

        task.status = target_status
        try:
            updated = self.task_repo.update(task)

            # Audit log status transition event
            audit_details = json.dumps({"from": old_status, "to": target_status})
            self.audit_repo.create(
                task_id=task.id,
                actor_id=user_id,
                action="status_change",
                details=audit_details
            )

            self._commit()
            return updated
        except Exception:
            self._rollback()
            raise

    def update_task(self, task_id: int, user_id: int, title: str, description: Optional[str] = None, due_date: Optional[str] = None) -> Task:
        task = self.get_task(task_id, user_id)
        if task.is_deleted:
            raise ValidationError("No se puede modificar una tarea eliminada.")

        if not title or not title.strip():
            raise ValidationError("El título de la tarea es obligatorio y no puede estar vacío.")

        cleaned_title = title.strip()
        if len(cleaned_title) > 150:
            raise ValidationError("El título de la tarea no puede exceder los 150 caracteres.")

        cleaned_description = description.strip() if description else None
        if cleaned_description and len(cleaned_description) > 1000:
            raise ValidationError("La descripción de la tarea no puede exceder los 1,000 caracteres.")

        cleaned_due_date = due_date.strip() if due_date else None

        changes = {}
        if task.title != cleaned_title:
            changes["title"] = {"old": task.title, "new": cleaned_title}
        if task.description != cleaned_description:
            changes["description"] = {"old": task.description, "new": cleaned_description}
        if task.due_date != cleaned_due_date:
            changes["due_date"] = {"old": task.due_date, "new": cleaned_due_date}

        task.title = cleaned_title
        task.description = cleaned_description
        task.due_date = cleaned_due_date

        try:
            updated = self.task_repo.update(task)

            if changes:
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="update",
                    details=json.dumps(changes)
                )

            self._commit()
            return updated
        except Exception:
            self._rollback()
            raise
