import sqlite3
from datetime import datetime, timezone
from typing import Optional, List
from src.domain.models import User, Task, AuditLog


class UserRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def create(self, email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email.strip().lower(), password_hash, now)
        )
        self.conn.commit()
        return User(id=cursor.lastrowid, email=email.strip().lower(), password_hash=password_hash, created_at=now)

    def get_by_id(self, user_id: int) -> Optional[User]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, email, password_hash, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return User(id=row[0], email=row[1], password_hash=row[2], created_at=row[3])
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, email, password_hash, created_at FROM users WHERE email = ? COLLATE NOCASE", (email.strip().lower(),))
        row = cursor.fetchone()
        if row:
            return User(id=row[0], email=row[1], password_hash=row[2], created_at=row[3])
        return None


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def create(self, user_id: int, title: str, description: Optional[str] = None, due_date: Optional[str] = None, status: str = "pendiente") -> Task:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO tasks (user_id, title, description, due_date, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title.strip(), description.strip() if description else None, due_date, status, now, now)
        )
        self.conn.commit()
        return Task(
            id=cursor.lastrowid,
            user_id=user_id,
            title=title.strip(),
            description=description.strip() if description else None,
            due_date=due_date,
            status=status,
            created_at=now,
            updated_at=now
        )

    def get_by_id(self, task_id: int) -> Optional[Task]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, user_id, title, description, due_date, status, created_at, updated_at FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        if row:
            return Task(
                id=row[0],
                user_id=row[1],
                title=row[2],
                description=row[3],
                due_date=row[4],
                status=row[5],
                created_at=row[6],
                updated_at=row[7]
            )
        return None

    def list_by_user(self, user_id: int, status: Optional[str] = None) -> List[Task]:
        cursor = self.conn.cursor()
        if status:
            cursor.execute(
                """SELECT id, user_id, title, description, due_date, status, created_at, updated_at
                   FROM tasks WHERE user_id = ? AND status = ?
                   ORDER BY created_at DESC, id DESC""",
                (user_id, status)
            )
        else:
            cursor.execute(
                """SELECT id, user_id, title, description, due_date, status, created_at, updated_at
                   FROM tasks WHERE user_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (user_id,)
            )
        rows = cursor.fetchall()
        return [
            Task(
                id=r[0],
                user_id=r[1],
                title=r[2],
                description=r[3],
                due_date=r[4],
                status=r[5],
                created_at=r[6],
                updated_at=r[7]
            )
            for r in rows
        ]

    def update(self, task: Task) -> Task:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE tasks SET title = ?, description = ?, due_date = ?, status = ?, updated_at = ?
               WHERE id = ?""",
            (task.title, task.description, task.due_date, task.status, now, task.id)
        )
        self.conn.commit()
        task.updated_at = now
        return task


class AuditLogRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def create(self, task_id: int, actor_id: int, action: str, details: str) -> AuditLog:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO audit_logs (task_id, actor_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, actor_id, action, details, now)
        )
        self.conn.commit()
        return AuditLog(id=cursor.lastrowid, task_id=task_id, actor_id=actor_id, action=action, details=details, created_at=now)

    def list_by_task(self, task_id: int) -> List[AuditLog]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, task_id, actor_id, action, details, created_at FROM audit_logs WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,)
        )
        rows = cursor.fetchall()
        return [
            AuditLog(
                id=r[0],
                task_id=r[1],
                actor_id=r[2],
                action=r[3],
                details=r[4],
                created_at=r[5]
            )
            for r in rows
        ]
