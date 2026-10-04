import pytest
from src.domain.exceptions import ValidationError, ConflictError, UnauthorizedError


def test_register_user_success(user_service):
    user = user_service.register_user("test@example.com", "password123")
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.password_hash != "password123"
    assert len(user.password_hash) > 20


def test_register_user_short_password_fails(user_service):
    with pytest.raises(ValidationError, match="al menos 8 caracteres"):
        user_service.register_user("test@example.com", "short")


def test_register_user_empty_or_spaces_password_fails(user_service):
    with pytest.raises(ValidationError, match="al menos 8 caracteres"):
        user_service.register_user("test@example.com", "        ")


def test_register_user_invalid_email_format(user_service):
    with pytest.raises(ValidationError, match="correo electrónico"):
        user_service.register_user("invalid-email-format", "password123")


def test_register_duplicate_email_fails(user_service):
    user_service.register_user("test@example.com", "password123")
    with pytest.raises(ConflictError, match="ya se encuentra registrado"):
        user_service.register_user("test@example.com", "anotherpassword123")


def test_authenticate_user_success(user_service):
    user_service.register_user("user@example.com", "securepwd123")
    authenticated_user = user_service.authenticate_user("user@example.com", "securepwd123")
    assert authenticated_user is not None
    assert authenticated_user.email == "user@example.com"


def test_authenticate_user_wrong_password_fails(user_service):
    user_service.register_user("user@example.com", "securepwd123")
    with pytest.raises(UnauthorizedError, match="Credenciales incorrectas"):
        user_service.authenticate_user("user@example.com", "wrongpassword")


def test_authenticate_nonexistent_user_fails(user_service):
    with pytest.raises(UnauthorizedError, match="Credenciales incorrectas"):
        user_service.authenticate_user("nobody@example.com", "password123")
