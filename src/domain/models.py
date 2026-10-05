from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    id: Optional[int]
    email: str
    password_hash: str
    created_at: str


@dataclass
class Task:
    id: Optional[int]
    user_id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    status: str = "pendiente"
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
