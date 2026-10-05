from enum import Enum
from src.domain.models import Task
from src.domain.exceptions import TaskNotAccessibleError, OperationNotPermittedError

class Operation(Enum):
    VIEW = "view"
    CHANGE_STATUS = "change_status"
    REOPEN = "reopen"
    EDIT = "edit"
    DELETE = "delete"
    MANAGE_ASSIGNMENT = "manage_assignment"

def authorize(task: Task, user_id: int, operation: Operation) -> None:
    """
    Evalúa si el user_id tiene permisos para realizar la operación solicitada
    sobre la tarea dada, según la matriz de colaboración.
    Lanza TaskNotAccessibleError (404) o OperationNotPermittedError (403).
    """
    # Si la tarea está eliminada, nadie tiene acceso
    if task.is_deleted:
        raise TaskNotAccessibleError(f"Task {task.id} is deleted or inaccessible.")

    # El propietario tiene acceso a todo
    if task.user_id == user_id:
        return

    # Si no es propietario y no es el asignado actual, no tiene acceso
    if task.assignee_id != user_id:
        raise TaskNotAccessibleError(f"User {user_id} does not have access to task {task.id}.")

    # Es el asignado actual. Verificamos la operación permitida.
    allowed_operations = {
        Operation.VIEW,
        Operation.CHANGE_STATUS,
        Operation.REOPEN,
    }

    if operation not in allowed_operations:
        raise OperationNotPermittedError(f"User {user_id} is an assignee but cannot perform {operation.value}.")
