import os

# Disable compiled C extensions in SQLAlchemy to ensure compatibility with Windows Application Control (WDAC)
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT", "1")
