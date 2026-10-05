from src.domain.exceptions import InvalidStateTransitionError

ALLOWED_STATUSES = {"pendiente", "en_progreso", "completada"}

VALID_TRANSITIONS = {
    "pendiente": {"en_progreso"},
    "en_progreso": {"completada"},
    "completada": set()  # No transitions allowed without explicit reopen workflow
}


class TaskStateMachine:
    """Finite state machine enforcing task lifecycle transitions."""

    @staticmethod
    def validate_transition(current_status: str, target_status: str) -> None:
        if current_status not in ALLOWED_STATUSES or target_status not in ALLOWED_STATUSES:
            raise InvalidStateTransitionError(f"Estado no reconocido: '{target_status}'.")

        if current_status == target_status:
            return

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            if current_status == "completada" and target_status == "pendiente":
                raise InvalidStateTransitionError(
                    "Transición no permitida: no es posible pasar de 'completada' a 'pendiente' sin reapertura explícita."
                )
            raise InvalidStateTransitionError(
                f"Transición no permitida de '{current_status}' a '{target_status}'."
            )

    @staticmethod
    def validate_reopen(current_status: str) -> str:
        """Validate that a task can be reopened. Only 'completada' can be reopened, moving to 'pendiente'."""
        if current_status != "completada":
            raise InvalidStateTransitionError(
                "Solo las tareas completadas pueden ser reabiertas."
            )
        return "pendiente"

