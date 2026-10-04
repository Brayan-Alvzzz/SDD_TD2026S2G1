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
