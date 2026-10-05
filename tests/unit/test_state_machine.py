import pytest
from src.domain.state_machine import TaskStateMachine
from src.domain.exceptions import InvalidStateTransitionError


def test_valid_transitions():
    # pendiente -> en_progreso
    TaskStateMachine.validate_transition("pendiente", "en_progreso")
    # en_progreso -> completada
    TaskStateMachine.validate_transition("en_progreso", "completada")
    # Same state is a no-op
    TaskStateMachine.validate_transition("pendiente", "pendiente")


def test_reopen_direct_transition_blocked():
    with pytest.raises(InvalidStateTransitionError, match="reapertura explícita"):
        TaskStateMachine.validate_transition("completada", "pendiente")


def test_completed_to_in_progress_blocked():
    with pytest.raises(InvalidStateTransitionError, match="Transición no permitida"):
        TaskStateMachine.validate_transition("completada", "en_progreso")


def test_skip_states_pending_to_completed_blocked():
    with pytest.raises(InvalidStateTransitionError, match="Transición no permitida"):
        TaskStateMachine.validate_transition("pendiente", "completada")


def test_unknown_state_fails():
    with pytest.raises(InvalidStateTransitionError, match="Estado no reconocido"):
        TaskStateMachine.validate_transition("pendiente", "cancelada")


def test_validate_reopen_from_completed_success():
    next_status = TaskStateMachine.validate_reopen("completada")
    assert next_status == "pendiente"


def test_validate_reopen_from_non_completed_fails():
    with pytest.raises(InvalidStateTransitionError, match="Solo las tareas completadas pueden ser reabiertas"):
        TaskStateMachine.validate_reopen("pendiente")

    with pytest.raises(InvalidStateTransitionError, match="Solo las tareas completadas pueden ser reabiertas"):
        TaskStateMachine.validate_reopen("en_progreso")

    with pytest.raises(InvalidStateTransitionError):
        TaskStateMachine.validate_reopen("invalido")

