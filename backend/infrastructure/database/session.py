# backend/app/infrastructure/database/session.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Engine assíncrono — conexão real com o PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # mostra SQL no log apenas em DEBUG
    pool_size=10,  # conexões simultâneas no pool
    max_overflow=20,  # conexões extras em pico de acesso
    pool_pre_ping=True,  # testa conexão antes de usar (evita erros)
)

# Fábrica de sessões
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # mantém objetos acessíveis após commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency do FastAPI — injeta sessão do banco nos endpoints.

    Uso no endpoint:
        async def meu_endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
