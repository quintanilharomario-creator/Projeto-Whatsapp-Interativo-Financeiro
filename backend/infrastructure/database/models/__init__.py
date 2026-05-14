# backend/app/infrastructure/database/models/__init__.py
# Importa todos os models aqui para o Alembic encontrar automaticamente
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.user import User

__all__ = ["Base", "User"]
