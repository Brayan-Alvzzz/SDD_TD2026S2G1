from datetime import datetime, timezone, timedelta
import secrets
import hashlib
import re
import json
from typing import Optional, List, Any, Union
from src.domain.models import User, Task, AuditLog, PasswordResetToken, Category, Notification
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError, NotFoundError, TaskNotAccessibleError
from src.domain.state_machine import TaskStateMachine
from src.domain.permissions import authorize, Operation
from src.infrastructure.security import hash_password, verify_password
from src.infrastructure.repositories import (
    UserRepository, TaskRepository, AuditLogRepository, PasswordResetTokenRepository, CategoryRepository, NotificationRepository
)
from src.infrastructure.notifications import ConsoleNotificationService

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: Optional[PasswordResetTokenRepository] = None,
        notification_service: Optional[Any] = None,
        session=None
    ):
        self.user_repo = user_repo
        self.session = session or getattr(user_repo, "session", None)
        self.token_repo = token_repo or (PasswordResetTokenRepository(self.session) if self.session is not None else None)
        self.notification_service = notification_service

    def is_delivery_configured(self) -> bool:
        """Check whether an active delivery mechanism is configured and enabled."""
        if self.notification_service is None:
            return False
        return bool(getattr(self.notification_service, "enabled", True))

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

    def request_password_reset(self, email: str, base_url: str = "") -> Optional[str]:
        if not email or not EMAIL_REGEX.match(email.strip()):
            raise ValidationError("Debe proporcionar una dirección de correo electrónico válida.")

        normalized_email = email.strip().lower()
        user = self.user_repo.get_by_email(normalized_email)
        delivery_active = self.is_delivery_configured()

        if user and delivery_active:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            now = datetime.now(timezone.utc)
            expires_at = (now + timedelta(minutes=30)).isoformat()

            try:
                if self.token_repo is not None:
                    # Revoke unconsumed previous tokens for this user
                    self.token_repo.revoke_all_for_user(user.id)
                    # Persist only the token SHA-256 hash
                    self.token_repo.create_token(
                        user_id=user.id,
                        token_hash=token_hash,
                        expires_at=expires_at
                    )
                self._commit()

                reset_url = f"{base_url}/reset-password/{raw_token}" if base_url else f"/reset-password/{raw_token}"
                self.notification_service.send_password_reset_link(user.email, reset_url)

                return raw_token
            except Exception:
                self._rollback()
                raise
        else:
            # Timing variation mitigation conforme a SC-004:
            # Execute dummy cryptographic hashing, dummy DB lookup, and calibrated delay.
            dummy_token = secrets.token_urlsafe(32)
            dummy_hash = hashlib.sha256(dummy_token.encode("utf-8")).hexdigest()
            if self.token_repo is not None:
                self.token_repo.find_active_by_hash(dummy_hash)
            import time
            time.sleep(0.005)
            return None


    def reset_password(self, token: str, new_password: str, new_password_confirm: str) -> None:
        if not new_password or not new_password_confirm:
            raise ValidationError("La contraseña y su confirmación son obligatorias.")

        if new_password != new_password_confirm:
            raise ValidationError("Las contraseñas no coinciden.")

        if len(new_password) < 8 or not new_password.strip():
            raise ValidationError("La contraseña debe tener al menos 8 caracteres.")

        if not token or not token.strip():
            raise ValidationError("El token de restablecimiento es inválido o ha expirado.")

        token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

        if self.token_repo is None:
            raise ValidationError("Repositorio de tokens no configurado.")

        token_obj = self.token_repo.find_active_by_hash(token_hash)
        if not token_obj:
            raise ValidationError("El token de restablecimiento es inválido o ha expirado.")

        # Expiration check
        try:
            token_expires = datetime.fromisoformat(token_obj.expires_at)
            if token_expires.tzinfo is None:
                token_expires = token_expires.replace(tzinfo=timezone.utc)
        except Exception:
            raise ValidationError("El token de restablecimiento es inválido o ha expirado.")

        now = datetime.now(timezone.utc)
        if token_expires < now:
            self.token_repo.mark_as_used(token_obj.id)
            self._commit()
            raise ValidationError("El token de restablecimiento ha expirado.")

        # Update password and consume token atomically
        new_pwd_hash = hash_password(new_password)
        try:
            self.user_repo.update_password(token_obj.user_id, new_pwd_hash)
            self.token_repo.mark_as_used(token_obj.id)
            self._commit()
        except Exception:
            self._rollback()
            raise



_NO_CHANGE = object()


class TaskService:
    def __init__(
        self,
        task_repo: TaskRepository,
        audit_repo: AuditLogRepository,
        category_repo: Optional[CategoryRepository] = None,
        session=None
    ):
        self.task_repo = task_repo
        self.audit_repo = audit_repo
        self.session = session or getattr(task_repo, "session", None) or getattr(audit_repo, "session", None)
        self.category_repo = category_repo or (CategoryRepository(self.session) if self.session is not None else None)

    @staticmethod
    def calculate_is_overdue(due_date: Optional[str], status: str, is_deleted: bool = False) -> bool:
        """Dynamic overdue calculation: due_date < today_utc, strictly excluding completed and deleted tasks."""
        if is_deleted or status == "completada":
            return False
        if not due_date or not due_date.strip():
            return False
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return due_date.strip() < today_utc

    @classmethod
    def _apply_overdue(cls, task: Optional[Task]) -> Optional[Task]:
        if task is None:
            return None
        task.is_overdue = cls.calculate_is_overdue(task.due_date, task.status, task.is_deleted)
        return task

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def create_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: str = "media",
        category_id: Optional[int] = None
    ) -> Task:
        if not title or not title.strip():
            raise ValidationError("El título de la tarea es obligatorio y no puede estar vacío.")

        cleaned_title = title.strip()
        if len(cleaned_title) > 150:
            raise ValidationError("El título de la tarea no puede exceder los 150 caracteres.")

        cleaned_description = description.strip() if description else None
        if cleaned_description and len(cleaned_description) > 1000:
            raise ValidationError("La descripción de la tarea no puede exceder los 1,000 caracteres.")

        cleaned_priority = (priority or "media").strip().lower() if isinstance(priority, str) else priority
        if cleaned_priority not in ("alta", "media", "baja"):
            raise ValidationError(f"Nivel de prioridad inválido: '{priority}'. Valores permitidos: alta, media, baja.")

        if category_id is not None:
            if self.category_repo is not None:
                cat = self.category_repo.get_by_id(category_id)
                if not cat:
                    raise NotFoundError(f"Categoría con id {category_id} no encontrada.")
                if cat.user_id != user_id:
                    raise UnauthorizedError("No tiene permiso para asociar una categoría ajena.")

        try:
            task = self.task_repo.create(
                user_id=user_id,
                title=cleaned_title,
                description=cleaned_description,
                due_date=due_date.strip() if due_date else None,
                status="pendiente",
                priority=cleaned_priority,
                category_id=category_id
            )

            # Audit log creation event
            audit_details = json.dumps({"title": task.title, "status": task.status, "priority": task.priority})
            self.audit_repo.create(
                task_id=task.id,
                actor_id=user_id,
                action="create",
                details=audit_details
            )

            self._commit()
            return self._apply_overdue(task)
        except Exception:
            self._rollback()
            raise

    def list_tasks(
        self,
        user_id: int,
        status: Optional[str] = None,
        sort: str = "created_desc",
        category_id: Optional[Union[int, str]] = None
    ) -> List[Task]:
        if status and status not in ("pendiente", "en_progreso", "completada"):
            raise ValidationError(f"Filtro de estado inválido: '{status}'.")
        valid_sorts = ("created_desc", "priority_desc", "priority_asc")
        if not sort or sort not in valid_sorts:
            sort = "created_desc"
        tasks = self.task_repo.list_by_user(user_id=user_id, status=status, sort=sort, category_id=category_id)
        return [self._apply_overdue(t) for t in tasks]

    def list_tasks_visible(
        self,
        user_id: int,
        role: str = "all",
        status: Optional[str] = None,
        sort: str = "created_desc",
        category_id: Optional[Union[int, str]] = None
    ) -> List[Task]:
        valid_roles = ("all", "owned", "assigned_to_me", "delegated")
        if role not in valid_roles:
            raise ValidationError(f"Filtro de rol inválido: '{role}'.")
        if status and status not in ("todas", "pendiente", "en_progreso", "completada"):
            raise ValidationError(f"Filtro de estado inválido: '{status}'.")
        valid_sorts = ("created_desc", "priority_desc", "priority_asc")
        if not sort or sort not in valid_sorts:
            raise ValidationError(f"Filtro de ordenamiento inválido: '{sort}'.")
            
        real_status = status if status != "todas" else None
            
        tasks = self.task_repo.list_visible(
            user_id=user_id,
            role=role,
            status=real_status,
            sort=sort,
            category_id=category_id
        )
        return [self._apply_overdue(t) for t in tasks]

    def get_task(self, task_id: int, user_id: int, include_deleted: bool = False, operation: Operation = Operation.VIEW) -> Task:
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Tarea no encontrada.")

        if include_deleted and task.is_deleted:
            # If explicitly included, we only allow the owner
            if task.user_id != user_id:
                raise TaskNotAccessibleError("No tiene permiso para acceder a esta tarea.")
        else:
            authorize(task, user_id, operation)

        return self._apply_overdue(task)

    def delete_task(self, task_id: int, user_id: int) -> Task:
        task = self.get_task(task_id, user_id, include_deleted=True, operation=Operation.DELETE)
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
            return self._apply_overdue(deleted)
        except Exception:
            self._rollback()
            raise

    def update_task_status(self, task_id: int, user_id: int, target_status: str) -> Task:
        task = self.get_task(task_id, user_id, operation=Operation.CHANGE_STATUS)
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
            return self._apply_overdue(updated)
        except Exception:
            self._rollback()
            raise

    def reopen_task(self, task_id: int, user_id: int) -> Task:
        task = self.get_task(task_id, user_id, include_deleted=True, operation=Operation.REOPEN)
        if task.is_deleted:
            raise NotFoundError("La tarea ya fue eliminada o no se encuentra disponible.")

        target_status = TaskStateMachine.validate_reopen(task.status)
        old_status = task.status
        task.status = target_status
        try:
            updated = self.task_repo.update(task)

            # Audit log reopen event
            audit_details = json.dumps({
                "from": old_status,
                "to": target_status,
                "reason": "reopen_by_user"
            })
            self.audit_repo.create(
                task_id=task.id,
                actor_id=user_id,
                action="reopen",
                details=audit_details
            )

            self._commit()
            return self._apply_overdue(updated)
        except Exception:
            self._rollback()
            raise

    def update_task_priority(self, task_id: int, user_id: int, priority: str) -> Task:
        cleaned_priority = (priority or "").strip().lower() if isinstance(priority, str) else priority
        if cleaned_priority not in ("alta", "media", "baja"):
            raise ValidationError(f"Nivel de prioridad inválido: '{priority}'. Valores permitidos: alta, media, baja.")

        task = self.get_task(task_id, user_id, operation=Operation.EDIT)
        if task.is_deleted:
            raise ValidationError("No se puede cambiar la prioridad de una tarea eliminada.")

        old_priority = task.priority
        if old_priority != cleaned_priority:
            task.priority = cleaned_priority
            try:
                updated = self.task_repo.update(task)
                audit_details = json.dumps({
                    "old_priority": old_priority,
                    "new_priority": cleaned_priority
                })
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="priority_change",
                    details=audit_details
                )
                self._commit()
                return self._apply_overdue(updated)
            except Exception:
                self._rollback()
                raise
        return self._apply_overdue(task)

    def update_task_category(self, task_id: int, user_id: int, category_id: Optional[int]) -> Task:
        task = self.get_task(task_id, user_id, operation=Operation.EDIT)
        if task.is_deleted:
            raise ValidationError("No se puede cambiar la categoría de una tarea eliminada.")

        if category_id is not None:
            if self.category_repo is not None:
                cat = self.category_repo.get_by_id(category_id)
                if not cat:
                    raise NotFoundError(f"Categoría con id {category_id} no encontrada.")
                if cat.user_id != user_id:
                    raise UnauthorizedError("No tiene permiso para asociar una categoría ajena.")

        old_category_id = task.category_id
        if old_category_id != category_id:
            task.category_id = category_id
            try:
                updated = self.task_repo.update(task)
                audit_details = json.dumps({
                    "old_category_id": old_category_id,
                    "new_category_id": category_id
                })
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="category_change",
                    details=audit_details
                )
                self._commit()
                return self._apply_overdue(updated)
            except Exception:
                self._rollback()
                raise
        return self._apply_overdue(task)

    def update_task(
        self,
        task_id: int,
        user_id: int,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        priority: Optional[str] = None,
        category_id: Any = _NO_CHANGE
    ) -> Task:
        task = self.get_task(task_id, user_id, operation=Operation.EDIT)
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

        priority_changed = False
        old_priority = task.priority
        if priority is not None:
            cleaned_priority = priority.strip().lower() if isinstance(priority, str) else priority
            if cleaned_priority not in ("alta", "media", "baja"):
                raise ValidationError(f"Nivel de prioridad inválido: '{priority}'. Valores permitidos: alta, media, baja.")
            if cleaned_priority != task.priority:
                priority_changed = True
                task.priority = cleaned_priority

        category_changed = False
        old_category_id = task.category_id
        if category_id is not _NO_CHANGE:
            if category_id is not None:
                if self.category_repo is not None:
                    cat = self.category_repo.get_by_id(category_id)
                    if not cat:
                        raise NotFoundError(f"Categoría con id {category_id} no encontrada.")
                    if cat.user_id != user_id:
                        raise UnauthorizedError("No tiene permiso para asociar una categoría ajena.")
            if task.category_id != category_id:
                category_changed = True
                task.category_id = category_id

        try:
            updated = self.task_repo.update(task)

            if changes:
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="update",
                    details=json.dumps(changes)
                )

            if priority_changed:
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="priority_change",
                    details=json.dumps({
                        "old_priority": old_priority,
                        "new_priority": task.priority
                    })
                )

            if category_changed:
                self.audit_repo.create(
                    task_id=task.id,
                    actor_id=user_id,
                    action="category_change",
                    details=json.dumps({
                        "old_category_id": old_category_id,
                        "new_category_id": task.category_id
                    })
                )

            self._commit()
            return self._apply_overdue(updated)
        except Exception:
            self._rollback()
            raise


class CategoryService:
    def __init__(self, category_repo: CategoryRepository, session=None):
        self.category_repo = category_repo
        self.session = session or getattr(category_repo, "session", None)

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def create_category(self, user_id: int, name: str) -> Category:
        if not name or not isinstance(name, str) or not name.strip():
            raise ValidationError("El nombre de la categoría es obligatorio y no puede estar vacío.")

        cleaned_name = name.strip()
        if len(cleaned_name) > 50:
            raise ValidationError("El nombre de la categoría no puede exceder los 50 caracteres.")

        existing = self.category_repo.get_by_user_and_name(user_id, cleaned_name)
        if existing:
            raise ConflictError(f"Ya posee una categoría con el nombre '{cleaned_name}'.")

        try:
            cat = self.category_repo.create(user_id, cleaned_name)
            self._commit()
            return cat
        except Exception:
            self._rollback()
            raise

    def list_categories(self, user_id: int) -> List[Category]:
        return self.category_repo.list_by_user(user_id)

    def get_category(self, category_id: int, user_id: int) -> Category:
        cat = self.category_repo.get_by_id(category_id)
        if not cat:
            raise NotFoundError("Categoría no encontrada.")
        if cat.user_id != user_id:
            raise UnauthorizedError("No tiene permiso para acceder a esta categoría.")
        return cat

    def delete_category(self, category_id: int, user_id: int) -> bool:
        self.get_category(category_id, user_id)
        try:
            deleted = self.category_repo.delete(category_id)
            self._commit()
            return deleted
        except Exception:
            self._rollback()
            raise


class CollaborationService:
    def __init__(
        self,
        task_repo: TaskRepository,
        user_repo: UserRepository,
        audit_repo: AuditLogRepository,
        notification_repo: NotificationRepository,
        session=None
    ):
        self.task_repo = task_repo
        self.user_repo = user_repo
        self.audit_repo = audit_repo
        self.notification_repo = notification_repo
        self.session = session or getattr(task_repo, "session", None)

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def assign_task(self, task_id: int, actor_id: int, assignee_email: str):
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Tarea no encontrada.")

        authorize(task, actor_id, Operation.MANAGE_ASSIGNMENT)

        if not assignee_email or not isinstance(assignee_email, str) or not assignee_email.strip():
            raise ValidationError("El correo del asignado es obligatorio.")

        assignee_email_clean = assignee_email.strip().lower()
        assignee = self.user_repo.get_by_email(assignee_email_clean)
        if not assignee:
            raise ValidationError(f"No se encontró un usuario con el correo {assignee_email_clean}.")

        if assignee.id == task.user_id:
            raise ValidationError("El propietario no puede auto-asignarse la tarea.")

        if task.assignee_id == assignee.id:
            return False, "none", assignee

        old_assignee_id = task.assignee_id
        action = "reassign" if old_assignee_id is not None else "assign"

        try:
            success = self.task_repo.set_assignee(task.id, old_assignee_id, assignee.id)
            if not success:
                raise ConflictError("La tarea fue modificada concurrentemente.")

            self.audit_repo.create(
                task_id=task.id,
                actor_id=actor_id,
                action=action,
                details=json.dumps({"old_assignee_id": old_assignee_id, "new_assignee_id": assignee.id})
            )

            actor = self.user_repo.get_by_id(actor_id)
            actor_email = actor.email if actor else "desconocido"
            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

            self.notification_repo.create(
                recipient_id=assignee.id,
                task_id=task.id,
                actor_id=actor_id,
                type="task_assigned",
                message=f"Asignada el {current_time} por {actor_email}"
            )

            self._commit()
            return True, action, assignee
        except Exception:
            self._rollback()
            raise

    def unassign_task(self, task_id: int, actor_id: int):
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Tarea no encontrada.")

        authorize(task, actor_id, Operation.MANAGE_ASSIGNMENT)

        if task.assignee_id is None:
            return False, "none", None

        old_assignee_id = task.assignee_id

        try:
            success = self.task_repo.set_assignee(task.id, old_assignee_id, None)
            if not success:
                raise ConflictError("La tarea fue modificada concurrentemente.")

            self.audit_repo.create(
                task_id=task.id,
                actor_id=actor_id,
                action="unassign",
                details=json.dumps({"old_assignee_id": old_assignee_id, "new_assignee_id": None})
            )

            self._commit()
            return True, "unassign", None
        except Exception:
            self._rollback()
            raise

class NotificationService:
    def __init__(self, notification_repo: NotificationRepository, session=None):
        self.notification_repo = notification_repo
        self.session = session or getattr(notification_repo, "session", None)

    def _commit(self):
        if self.session is not None:
            self.session.commit()

    def _rollback(self):
        if self.session is not None:
            self.session.rollback()

    def list_notifications(self, user_id: int) -> List[Notification]:
        return self.notification_repo.list_by_recipient(user_id)

    def count_unread(self, user_id: int) -> int:
        return self.notification_repo.count_unread(user_id)

    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        # Fetch the notification to check existence and ownership
        notif = self.notification_repo.get_by_id_and_recipient(notification_id, user_id)
        if not notif:
            raise NotFoundError("Notificación no encontrada o no pertenece al usuario.")

        if notif.is_read:
            return True

        try:
            self.notification_repo.mark_as_read(notification_id, user_id)
            self._commit()
            return True
        except Exception:
            self._rollback()
            raise
