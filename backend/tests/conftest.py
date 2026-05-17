import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.infrastructure.database.models  # noqa: F401 — registers all models with Base.metadata
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.session import get_db
from app.main import app
from app.services.auth_service import AuthService

TEST_DATABASE_URL = "postgresql+asyncpg://saas_user:dev_password_123@localhost:5432/saas_financeiro_test"


def _make_engine():
    return create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)


# Fixture sync para criar/dropar as tabelas uma vez por sessão de testes.
# Usa asyncio.run() isolado para não conflitar com os event loops do pytest-asyncio.
@pytest.fixture(scope="session", autouse=True)
def ensure_test_tables():
    async def _create():
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_create())
    yield

    async def _drop():
        engine = _make_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_drop())


# Engine criado DENTRO da fixture function-scoped → mesma event loop que o teste.
@pytest_asyncio.fixture
async def db(ensure_test_tables):
    engine = _make_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE whatsapp_messages, goals, conversation_states, users"
                " RESTART IDENTITY CASCADE"
            )
        )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db: AsyncSession):
    return await AuthService.register(
        email="existing@test.com",
        password="TestPass123!",
        full_name="Test User",
        db=db,
    )


@pytest.fixture(autouse=True)
def mock_redis_globally():
    """Prevents real Redis connections in all tests (Redis not available in test env)."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.setex = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.keys = AsyncMock(return_value=[])
    with patch(
        "app.infrastructure.cache.redis_client.redis.from_url", return_value=mock_client
    ):
        import app.infrastructure.cache.redis_client as m

        original = m._redis
        m._redis = None
        yield mock_client
        m._redis = original


@pytest.fixture
def mock_claude_provider():
    """Patches ClaudeProvider._call to prevent real API calls in tests."""
    with patch(
        "app.infrastructure.ai.claude_provider.ClaudeProvider._call"
    ) as mock_call:
        mock_call.return_value = AsyncMock(
            return_value='{"type":"EXPENSE","category":"Outros","amount":null,"confidence":0.5,"explanation":"mock"}'
        )
        yield mock_call


@pytest.fixture
def mock_ai_service():
    """Patches AIService entirely for endpoint/service integration tests."""
    with patch("app.services.ai_service.AIService") as MockClass:
        instance = MagicMock()
        instance.analyze_transaction = AsyncMock()
        instance.generate_monthly_report = AsyncMock()
        instance.answer_question = AsyncMock()
        instance.enhance_whatsapp_response = AsyncMock(
            side_effect=lambda msg, *a, **kw: msg
        )
        MockClass.return_value = instance
        yield instance
