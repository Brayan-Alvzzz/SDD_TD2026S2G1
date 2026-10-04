"""Domain exceptions for TaskControl."""

class DomainError(Exception):
    """Base domain exception."""
    pass


class ValidationError(DomainError):
    """Raised when an entity or input fails validation rules."""
    pass


class UnauthorizedError(DomainError):
    """Raised when an operation is requested without proper authorization or authentication."""
    pass


class NotFoundError(DomainError):
    """Raised when a requested resource is not found."""
    pass


class ConflictError(DomainError):
    """Raised when an action conflicts with existing data (e.g. duplicate email)."""
    pass


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid task state transition is requested."""
    pass
