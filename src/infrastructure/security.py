"""Security and password utilities for TaskControl."""
from werkzeug.security import generate_password_hash, check_password_hash
from src.domain.exceptions import ValidationError


def hash_password(password: str) -> str:
    """Hash password using Werkzeug's default secure salted method (scrypt or pbkdf2)."""
    if not password or len(password) < 8:
        raise ValidationError("La contraseña debe tener al menos 8 caracteres.")
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify raw password against stored salted hash."""
    if not password or not password_hash:
        return False
    return check_password_hash(password_hash, password)
