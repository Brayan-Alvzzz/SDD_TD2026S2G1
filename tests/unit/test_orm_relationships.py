import pytest
import sqlalchemy as sa
from src.infrastructure.models import UserORM, TaskORM

def test_task_owner_assignee_relationship(db_session, user_repo, task_repo):
    """
    La tarea pertenece a A.tasks y task.user corresponde a A;
    asignarla a B no la convierte en una tarea creada por B.
    """
    # 1. Crear usuario A (propietario) y usuario B (asignado)
    user_a = user_repo.create("propietario@example.com", "hash")
    user_b = user_repo.create("asignado@example.com", "hash")
    db_session.commit()
    
    # 2. A crea una tarea
    task = task_repo.create(user_a.id, "Tarea de A")
    
    # 3. Asignar a B (directamente a ORM para validar las relaciones)
    task_orm = db_session.get(TaskORM, task.id)
    task_orm.assignee_id = user_b.id
    db_session.flush()
    
    # Refrescar usuarios
    user_a_orm = db_session.get(UserORM, user_a.id)
    user_b_orm = db_session.get(UserORM, user_b.id)
    
    # 4. Validar relaciones
    # La tarea debe estar en la colección 'tasks' de A
    assert any(t.id == task.id for t in user_a_orm.tasks), "La tarea debe permanecer en la colección tasks del creador A"
    
    # La tarea NO debe estar en la colección 'tasks' de B (a menos que diseñemos una colección asignadas, pero 'tasks' es creadas)
    assert not any(t.id == task.id for t in user_b_orm.tasks), "La tarea no debe aparecer en la colección tasks del asignado B"
    
    # task_orm.user debe seguir siendo A
    assert task_orm.user.id == user_a.id, "El creador de la tarea debe seguir siendo A"
