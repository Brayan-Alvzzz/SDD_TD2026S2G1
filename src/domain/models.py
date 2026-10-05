from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: Optional[int]
    email: str
    password_hash: str
    created_at: str


@dataclass
class Category:
    id: Optional[int]
    user_id: int
    name: str
    created_at: str = ""
    task_count: int = 0


@dataclass
class Task:
    id: Optional[int]
    user_id: int
    title: str
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None
    status: str = "pendiente"
    priority: str = "media"
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_overdue: bool = False
    is_deleted: bool = False
    deleted_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AuditLog:
    id: Optional[int]
    task_id: int
    actor_id: int
    action: str
    details: str
    created_at: str


@dataclass
class PasswordResetToken:
    id: Optional[int]
    user_id: int
    token_hash: str
    expires_at: str
    used: bool = False
    created_at: str = ""

