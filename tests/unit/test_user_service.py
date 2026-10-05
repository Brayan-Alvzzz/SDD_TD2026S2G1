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


def test_request_password_reset_registered_email_success(user_service):
    import hashlib
    user = user_service.register_user("pwd_reset_user@example.com", "oldpassword123")
    token = user_service.request_password_reset("pwd_reset_user@example.com")

    assert token is not None
    assert isinstance(token, str)
    assert len(token) >= 32

    # Verify SHA-256 hash is what is stored in repo, not the plain text token
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    stored = user_service.token_repo.find_active_by_hash(token_hash)
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.used is False
    assert stored.expires_at is not None


def test_request_password_reset_nonexistent_email_neutral(user_service):
    token = user_service.request_password_reset("nobody_exists@example.com")
    # Must not leak user existence: returns None internally for email sending, no exception raised
    assert token is None


def test_request_password_reset_invalid_email_format(user_service):
    with pytest.raises(ValidationError, match="correo electrónico"):
        user_service.request_password_reset("not-a-valid-email")

    with pytest.raises(ValidationError, match="correo electrónico"):
        user_service.request_password_reset("")


def test_request_password_reset_revokes_previous_tokens(user_service):
    import hashlib
    user_service.register_user("multi_token@example.com", "oldpassword123")

    token1 = user_service.request_password_reset("multi_token@example.com")
    hash1 = hashlib.sha256(token1.encode("utf-8")).hexdigest()
    assert user_service.token_repo.find_active_by_hash(hash1) is not None

    token2 = user_service.request_password_reset("multi_token@example.com")
    hash2 = hashlib.sha256(token2.encode("utf-8")).hexdigest()

    # Previous token1 must now be revoked (not active)
    assert user_service.token_repo.find_active_by_hash(hash1) is None
    # Most recent token2 must be active
    assert user_service.token_repo.find_active_by_hash(hash2) is not None


def test_reset_password_success(user_service):
    user_service.register_user("reset_ok@example.com", "oldpassword123")
    token = user_service.request_password_reset("reset_ok@example.com")

    user_service.reset_password(token, "brandnewpassword123", "brandnewpassword123")

    # Old password no longer works
    with pytest.raises(UnauthorizedError):
        user_service.authenticate_user("reset_ok@example.com", "oldpassword123")

    # New password works
    auth_user = user_service.authenticate_user("reset_ok@example.com", "brandnewpassword123")
    assert auth_user is not None


def test_reset_password_single_use_cannot_reuse(user_service):
    user_service.register_user("single_use@example.com", "oldpassword123")
    token = user_service.request_password_reset("single_use@example.com")

    user_service.reset_password(token, "brandnewpassword123", "brandnewpassword123")

    # Second attempt with same token must fail
    with pytest.raises(ValidationError, match="inválido o ha expirado"):
        user_service.reset_password(token, "anotherpassword123", "anotherpassword123")


def test_reset_password_expired_token(user_service):
    import hashlib
    from datetime import datetime, timezone, timedelta
    user = user_service.register_user("expired_token@example.com", "oldpassword123")

    raw_token = "expired_raw_token_value_12345678"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    past_expiration = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    user_service.token_repo.create_token(user_id=user.id, token_hash=token_hash, expires_at=past_expiration)

    with pytest.raises(ValidationError, match="ha expirado"):
        user_service.reset_password(raw_token, "brandnewpassword123", "brandnewpassword123")


def test_reset_password_validation_failures(user_service):
    user_service.register_user("val_failures@example.com", "oldpassword123")
    token = user_service.request_password_reset("val_failures@example.com")

    # Passwords mismatch
    with pytest.raises(ValidationError, match="no coinciden"):
        user_service.reset_password(token, "brandnewpassword123", "differentpassword123")

    # Password shorter than 8 characters
    with pytest.raises(ValidationError, match="al menos 8 caracteres"):
        user_service.reset_password(token, "short7", "short7")

    # Completely invalid/unknown token
    with pytest.raises(ValidationError, match="inválido"):
        user_service.reset_password("unknown_fake_token", "brandnewpassword123", "brandnewpassword123")


def test_console_notification_service_local_terminal_only(capsys, user_service):
    user_service.register_user("terminal_user@example.com", "oldpassword123")
    token = user_service.request_password_reset("terminal_user@example.com", base_url="http://localhost:5000")

    captured = capsys.readouterr()
    # Verified: link is printed to terminal stdout for local dev testing
    assert "[DESARROLLO LOCAL - RECUPERACIÓN DE CONTRASEÑA]" in captured.out
    assert "http://localhost:5000/reset-password/" in captured.out
    assert token in captured.out


def test_when_delivery_not_configured_does_not_issue_or_revoke_tokens(user_repo, db_session):
    """Verify that without a configured delivery mechanism, request_password_reset

    does not issue new tokens nor revoke existing ones that the user cannot receive.
    """
    from src.domain.services import UserService
    from src.infrastructure.repositories import PasswordResetTokenRepository
    from src.infrastructure.models import PasswordResetTokenORM

    token_repo = PasswordResetTokenRepository(db_session)
    # Service with NO delivery mechanism configured (notification_service=None)
    service_unconfigured = UserService(user_repo, token_repo=token_repo, notification_service=None, session=db_session)

    user = service_unconfigured.register_user("no_delivery@example.com", "validpassword123")

    # Manually create an existing active token to test it is NOT revoked
    import hashlib
    initial_hash = hashlib.sha256(b"existing_active_token").hexdigest()
    token_repo.create_token(user_id=user.id, token_hash=initial_hash, expires_at="2099-01-01T00:00:00")
    db_session.commit()

    # Request reset with no delivery mechanism
    res = service_unconfigured.request_password_reset("no_delivery@example.com")
    assert res is None

    # Verify:
    # 1. Previous active token was NOT revoked
    prev = token_repo.find_active_by_hash(initial_hash)
    assert prev is not None
    assert prev.used is False

    # 2. No new token was created
    all_tokens = db_session.query(PasswordResetTokenORM).filter_by(user_id=user.id).all()
    assert len(all_tokens) == 1


def test_timing_mitigation_between_existing_and_nonexistent_email(user_service):
    """Verify reasonable timing mitigation between registered and unregistered emails (SC-004).

    Confirms that dummy operations and calibrated time alignment mitigate significant variations,
    without asserting absolute mathematical side-channel immunity.
    """
    user_service.register_user("timing_existing@example.com", "password123")

    import time
    # Warm-up run to prime caches
    user_service.request_password_reset("timing_existing@example.com")
    user_service.request_password_reset("timing_unregistered@example.com")

    # Time existing account
    t0 = time.perf_counter()
    user_service.request_password_reset("timing_existing@example.com")
    duration_existing = time.perf_counter() - t0

    # Time nonexistent account
    t1 = time.perf_counter()
    user_service.request_password_reset("timing_unregistered@example.com")
    duration_nonexistent = time.perf_counter() - t1

    # Verify that variation is reasonably mitigated (under 100ms in local testing)
    diff = abs(duration_existing - duration_nonexistent)
    assert diff < 0.1, (
        f"Significant timing variation detected: existing={duration_existing:.4f}s, "
        f"nonexistent={duration_nonexistent:.4f}s (difference={diff:.4f}s)"
    )



