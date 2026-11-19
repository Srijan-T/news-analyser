"""Database models. Import them here so Alembic's autogenerate sees every table.

Tables arrive with the features that use them (searches and articles next, then analyses),
so each migration in the history has a reason to exist.
"""

from app.db import Base

__all__ = ["Base"]
