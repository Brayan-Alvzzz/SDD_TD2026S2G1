import pytest
from src.domain.models import Task
from src.domain.exceptions import TaskNotAccessibleError, OperationNotPermittedError
from src.domain.permissions import authorize, Operation

def test_owner_full_access():
    """El propietario tiene acceso total a todas las operaciones si la tarea no está eliminada."""
    task = Task(id=1, user_id=10, title="Task", status="pendiente", is_deleted=False)
    
    # Debe pasar sin lanzar excepción
    authorize(task, user_id=10, operation=Operation.VIEW)
    authorize(task, user_id=10, operation=Operation.CHANGE_STATUS)
    authorize(task, user_id=10, operation=Operation.REOPEN)
    authorize(task, user_id=10, operation=Operation.EDIT)
    authorize(task, user_id=10, operation=Operation.DELETE)
    authorize(task, user_id=10, operation=Operation.MANAGE_ASSIGNMENT)

def test_assignee_partial_access():
    """El asignado actual solo puede ver, cambiar estado y reabrir."""
    task = Task(id=1, user_id=10, assignee_id=20, title="Task", status="pendiente", is_deleted=False)
    
    # Permitidas
    authorize(task, user_id=20, operation=Operation.VIEW)
    authorize(task, user_id=20, operation=Operation.CHANGE_STATUS)
    authorize(task, user_id=20, operation=Operation.REOPEN)
    
    # Denegadas (403)
    with pytest.raises(OperationNotPermittedError):
        authorize(task, user_id=20, operation=Operation.EDIT)
    with pytest.raises(OperationNotPermittedError):
        authorize(task, user_id=20, operation=Operation.DELETE)
    with pytest.raises(OperationNotPermittedError):
        authorize(task, user_id=20, operation=Operation.MANAGE_ASSIGNMENT)

def test_alien_user_no_access():
    """Un usuario ajeno no tiene acceso a la tarea (404)."""
    task = Task(id=1, user_id=10, assignee_id=20, title="Task", status="pendiente", is_deleted=False)
    
    # Todas las operaciones denegadas con 404
    operations = [
        Operation.VIEW, Operation.CHANGE_STATUS, Operation.REOPEN,
        Operation.EDIT, Operation.DELETE, Operation.MANAGE_ASSIGNMENT
    ]
    for op in operations:
        with pytest.raises(TaskNotAccessibleError):
            authorize(task, user_id=99, operation=op)

def test_past_assignee_no_access():
    """Un usuario que fue desasignado no tiene acceso (404)."""
    task = Task(id=1, user_id=10, assignee_id=None, title="Task", status="pendiente", is_deleted=False)
    
    # El usuario 20 era asignado pero ya no lo es. Actúa como ajeno.
    with pytest.raises(TaskNotAccessibleError):
        authorize(task, user_id=20, operation=Operation.VIEW)

def test_deleted_task_no_access():
    """Nadie, ni propietario ni asignado, tiene acceso a una tarea eliminada."""
    task = Task(id=1, user_id=10, assignee_id=20, title="Task", status="pendiente", is_deleted=True)
    
    operations = [
        Operation.VIEW, Operation.CHANGE_STATUS, Operation.REOPEN,
        Operation.EDIT, Operation.DELETE, Operation.MANAGE_ASSIGNMENT
    ]
    
    for op in operations:
        # Propietario no tiene acceso (404)
        with pytest.raises(TaskNotAccessibleError):
            authorize(task, user_id=10, operation=op)
            
        # Asignado no tiene acceso (404)
        with pytest.raises(TaskNotAccessibleError):
            authorize(task, user_id=20, operation=op)
