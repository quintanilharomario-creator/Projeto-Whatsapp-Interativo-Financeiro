"""
Ponto de entrada da aplicação FastAPI.

Este arquivo:
1. Cria a instância do FastAPI
2. Configura logging no startup
3. Registra middlewares (CORS)
4. Define o endpoint de health check
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida da aplicação.
    Antes do yield  → startup
    Depois do yield → shutdown
    """
    # STARTUP
    setup_logging()
    logger.info(
        "aplicacao_iniciando",
        app=settings.APP_NAME,
        versao=settings.APP_VERSION,
        ambiente=settings.ENVIRONMENT,
    )

    yield  # aplicação roda aqui

    # SHUTDOWN
    logger.info("aplicacao_encerrando", app=settings.APP_NAME)


# Instância principal do FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SaaS Financeiro com WhatsApp + IA",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — permite o frontend chamar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if settings.is_development
        else [settings.FRONTEND_URL]
    ),
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
