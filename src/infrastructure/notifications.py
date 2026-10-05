"""Console notification service for local development and testing.

Prints password reset links solely to the server terminal (stdout).
Never persists plain tokens to disk or application logs.
"""
import sys


class ConsoleNotificationService:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def send_password_reset_link(self, email: str, reset_url: str) -> None:
        """Print password reset link exclusively to the server terminal during local development when enabled."""
        if not self.enabled:
            return

        banner = (
            f"\n=======================================================\n"
            f"[DESARROLLO LOCAL - RECUPERACIÓN DE CONTRASEÑA]\n"
            f"Para: {email}\n"
            f"Enlace de restablecimiento (válido por 30 minutos):\n"
            f"{reset_url}\n"
            f"=======================================================\n"
        )
        print(banner, file=sys.stdout, flush=True)

