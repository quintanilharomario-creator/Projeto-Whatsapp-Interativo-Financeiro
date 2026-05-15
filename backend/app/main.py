"""
Ponto de entrada da aplicação FastAPI.

Este arquivo:
1. Cria a instância do FastAPI
2. Configura logging no startup
3. Registra middlewares (CORS)
4. Define o endpoint de health check
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_ALEMBIC_INI))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "aplicacao_iniciando",
        app=settings.APP_NAME,
        versao=settings.APP_VERSION,
        ambiente=settings.ENVIRONMENT,
    )

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_migrations)
        logger.info("migrations_aplicadas")
    except Exception as exc:
        logger.error("migrations_erro", error=str(exc))

    yield

    logger.info("aplicacao_encerrando", app=settings.APP_NAME)


# Instância principal do FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Hermes by Quingo — Suas finanças no WhatsApp",
    contact={"name": "Quingo", "email": "adminquingo@quingo.com.br"},
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — permite o frontend chamar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=(["*"] if settings.is_development else [settings.FRONTEND_URL]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(api_router)


@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    Verifica se a aplicação está rodando.
    Usado por Docker, load balancers e monitoramento.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "versao": settings.APP_VERSION,
        "ambiente": settings.ENVIRONMENT,
    }
