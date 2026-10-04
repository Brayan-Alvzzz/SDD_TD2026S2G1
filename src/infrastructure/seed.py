"""Database seeding script for local demo and testing."""
import os
from src.infrastructure.database import get_db_connection, init_db_schema
from src.infrastructure.repositories import UserRepository, TaskRepository, AuditLogRepository
from src.domain.services import UserService, TaskService


def seed_database(db_path: str = "taskcontrol.db"):
    print(f"Connecting to {db_path}...")
    conn = get_db_connection(db_path)
    init_db_schema(conn)

    user_repo = UserRepository(conn)
    task_repo = TaskRepository(conn)
    audit_repo = AuditLogRepository(conn)

    user_service = UserService(user_repo)
    task_service = TaskService(task_repo, audit_repo)

    demo_email = "demo@taskcontrol.com"
    demo_password = "password123"

    user = user_repo.get_by_email(demo_email)
    if not user:
        print(f"Creating demo user: {demo_email}")
        user = user_service.register_user(demo_email, demo_password)
    else:
        print(f"Demo user already exists (id={user.id})")

    # Sample tasks
    sample_tasks = [
        ("Definir arquitectura de base de datos", "Crear tablas con claves foráneas en SQLite", "2026-10-05", "completada"),
        ("Implementar autenticación segura", "Registro y login con cookies HttpOnly de 24 horas", "2026-10-10", "en_progreso"),
        ("Diseñar interfaz responsiva", "Plantillas Jinja2 y hojas de estilo CSS", "2026-10-15", "pendiente"),
        ("Configurar pruebas de integración", "Cobertura completa con pytest para rutas críticas", "2026-10-20", "pendiente"),
    ]

    existing_tasks = task_service.list_tasks(user.id)
    if not existing_tasks:
        print("Inserting sample tasks...")
        for title, desc, due, status in sample_tasks:
            t = task_service.create_task(user.id, title, desc, due)
            if status != "pendiente":
                task_service.update_task_status(t.id, user.id, "en_progreso")
                if status == "completada":
                    task_service.update_task_status(t.id, user.id, "completada")
        print(f"Successfully seeded {len(sample_tasks)} tasks.")
    else:
        print(f"Database already contains {len(existing_tasks)} tasks for demo user.")

    conn.close()
    print("Database seeding completed.")


if __name__ == "__main__":
    db_file = os.environ.get("DATABASE_PATH", "taskcontrol.db")
    seed_database(db_file)
