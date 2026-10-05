import pytest
from datetime import datetime, timezone
import sqlalchemy as sa
from src.domain.models import Task, User
from src.infrastructure.models import TaskORM

try:
    from src.domain.models import Notification
    from src.infrastructure.repositories import NotificationRepository
except ImportError:
    Notification = None
    NotificationRepository = None

@pytest.fixture
def repo(db_session):
    if NotificationRepository is None:
        pytest.fail("NotificationRepository not implemented yet")
    return NotificationRepository(db_session)

@pytest.fixture
def users(user_repo, db_session):
    u1 = user_repo.create("owner@example.com", "hash")
    u2 = user_repo.create("assignee@example.com", "hash")
    u3 = user_repo.create("other@example.com", "hash")
    db_session.commit()
    return u1, u2, u3

@pytest.fixture
def task_obj(task_repo, users, db_session):
    owner, assignee, _ = users
    task = task_repo.create(owner.id, "Test Task")
    # Asignamos directamente en BD para la prueba
    stmt = sa.update(TaskORM).where(TaskORM.id == task.id).values(assignee_id=assignee.id)
    db_session.execute(stmt)
    db_session.commit()
    return task_repo.get_by_id(task.id)

def test_notification_insertion_base(repo, users, task_obj):
    """
    Verifica que la notificación se inserta correctamente y sus campos
    coinciden con el modelo y la especificación.
    """
    owner, assignee, _ = users
    message = "owner@example.com te asignó una tarea"
    
    notif = repo.create(
        recipient_id=assignee.id,
        task_id=task_obj.id,
        actor_id=owner.id,
        type="task_assigned",
        message=message
    )
    
    assert notif.id is not None
    assert notif.recipient_id == assignee.id
    assert notif.task_id == task_obj.id
    assert notif.actor_id == owner.id
    assert notif.type == "task_assigned"
    assert notif.message == message
    assert notif.is_read is False
    assert notif.read_at is None
    assert notif.created_at is not None

def test_notification_isolation(repo, users, task_obj, task_repo, db_session):
    """Aislamiento entre destinatarios en las consultas previstas."""
    owner, assignee, other = users
    
    # owner asigna a assignee
    repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "msg 1")
    
    # owner asigna otra tarea a other
    task2 = task_repo.create(owner.id, "Task 2")
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task2.id).values(assignee_id=other.id))
    db_session.commit()
    repo.create(other.id, task2.id, owner.id, "task_assigned", "msg 2")
    
    # Consultamos las de assignee
    notifs_assignee = repo.list_by_recipient(assignee.id)
    assert len(notifs_assignee) == 1
    assert notifs_assignee[0].recipient_id == assignee.id
    
    # Consultamos las de other
    notifs_other = repo.list_by_recipient(other.id)
    assert len(notifs_other) == 1
    assert notifs_other[0].recipient_id == other.id

def test_notification_available_view_and_loss_of_access(repo, users, task_obj, db_session):
    """
    Disponibilidad de navegación según acceso.
    Pérdida tras desasignación, reasignación o eliminación.
    Tras reasignar nuevamente al mismo usuario, solo la nueva permite navegar.
    Las históricas se conservan con su mensaje.
    """
    owner, assignee, other = users
    
    # 1. Asignamos a assignee
    n1 = repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "asignación 1")
    notifs = repo.list_by_recipient(assignee.id)
    assert len(notifs) == 1
    assert getattr(notifs[0], "available", False) is True, "Debe estar disponible porque es el asignado vigente"
    
    # 2. Desasignar (assignee_id = None)
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task_obj.id).values(assignee_id=None))
    db_session.commit()
    
    notifs = repo.list_by_recipient(assignee.id)
    assert len(notifs) == 1
    assert notifs[0].available is False, "Se pierde disponibilidad tras desasignar"
    assert notifs[0].message == "asignación 1", "El historial conserva el mensaje"
    
    # 3. Reasignar a other
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task_obj.id).values(assignee_id=other.id))
    db_session.commit()
    repo.create(other.id, task_obj.id, owner.id, "task_assigned", "asignación a otro")
    
    notifs_assignee = repo.list_by_recipient(assignee.id)
    assert notifs_assignee[0].available is False, "Sigue sin disponibilidad tras reasignar a otro"
    
    notifs_other = repo.list_by_recipient(other.id)
    assert notifs_other[0].available is True, "El nuevo asignado sí la tiene disponible"
    
    # 4. Reasignar nuevamente al mismo (assignee original)
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task_obj.id).values(assignee_id=assignee.id))
    db_session.commit()
    n3 = repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "asignación nueva")
    
    notifs = repo.list_by_recipient(assignee.id)
    assert len(notifs) == 2
    # La antigua debe ser available=False, la nueva available=True
    n_old = next(n for n in notifs if n.id == n1.id)
    n_new = next(n for n in notifs if n.id == n3.id)
    assert n_old.available is False, "Solo la última notificación permite navegar (MAX id)"
    assert n_new.available is True
    
    # 5. Eliminación de la tarea (is_deleted = True)
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task_obj.id).values(is_deleted=True))
    db_session.commit()
    
    notifs = repo.list_by_recipient(assignee.id)
    assert all(n.available is False for n in notifs), "La eliminación quita disponibilidad a todas"

def test_notification_unread_count(repo, users, task_obj):
    """Prueba el contador de no leídas."""
    owner, assignee, _ = users
    
    assert repo.count_unread(assignee.id) == 0
    
    n1 = repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "msg")
    assert repo.count_unread(assignee.id) == 1
    
    repo.mark_as_read(n1.id, assignee.id)
    assert repo.count_unread(assignee.id) == 0

def test_notification_rollback(repo, users, task_obj, db_session):
    """Comprueba que una inserción puede revertirse con rollback."""
    owner, assignee, _ = users
    
    repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "msg rollback")
    db_session.rollback()
    
    assert repo.count_unread(assignee.id) == 0
    assert len(repo.list_by_recipient(assignee.id)) == 0

def test_notification_global_max_id_isolation(repo, users, task_obj, task_repo, db_session):
    """
    Comprueba que las pruebas incluyen varias tareas y varios destinatarios,
    para detectar un MAX(id) global incorrecto.
    """
    owner, assignee, other = users
    
    # owner asigna task_obj a assignee
    repo.create(assignee.id, task_obj.id, owner.id, "task_assigned", "msg 1 para assignee")
    
    # owner crea task2 y asigna a other
    task2 = task_repo.create(owner.id, "Task 2")
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task2.id).values(assignee_id=other.id))
    db_session.commit()
    repo.create(other.id, task2.id, owner.id, "task_assigned", "msg 1 para other")
    
    # owner crea task3 y asigna a assignee
    task3 = task_repo.create(owner.id, "Task 3")
    db_session.execute(sa.update(TaskORM).where(TaskORM.id == task3.id).values(assignee_id=assignee.id))
    db_session.commit()
    repo.create(assignee.id, task3.id, owner.id, "task_assigned", "msg 2 para assignee")
    
    # Consultamos
    notifs_assignee = repo.list_by_recipient(assignee.id)
    assert len(notifs_assignee) == 2
    # Ambas de assignee deben estar disponibles porque MAX(id) es particionado por (task_id, recipient_id)
    for n in notifs_assignee:
        assert getattr(n, "available", False) is True, f"Notificación {n.id} para {n.task_id} debe estar available"
    
    notifs_other = repo.list_by_recipient(other.id)
    assert len(notifs_other) == 1
    assert getattr(notifs_other[0], "available", False) is True, "Notificación para other debe estar available"

