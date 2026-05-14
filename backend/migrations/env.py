from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Importa a Base e os models usando o caminho correto (backend.app)
from backend.app.db.base import Base
import backend.app.db.models.user  # garante que o User seja reconhecido

# Configuração do Alembic
config = context.config

# Logging padrão do Alemb
