"""
Configurações centrais da aplicação.
Usa Pydantic Settings para carregar e validar variáveis de ambiente.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ambiente
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    TESTING: bool = False

    # Aplicação
    APP_NAME: str = "SaaS Financeiro"
    APP_VERSION: str = "0.1.0"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # Segurança
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Banco de dados
    DATABASE_URL: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "saas_user"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "saas_financeiro"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    CACHE_TTL: int = 300

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Inteligência Artificial
    AI_PROVIDER: Literal["openai", "claude"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
    AI_TEMPERATURE: float = 0.3

    # Áudio
    WHISPER_MODEL: str = "whisper-1"
    TTS_PROVIDER: str = "openai"
    TTS_VOICE: str = "nova"
    ELEVENLABS_API_KEY: str = ""

    # WhatsApp
    WHATSAPP_PROVIDER: Literal["cloud_api", "evolution", "baileys"] = "cloud_api"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"

    # Storage
    STORAGE_PROVIDER: Literal["local", "s3", "minio"] = "minio"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "saas-files"
    MINIO_USE_SSL: bool = False
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = ""

    # Memória Semântica
    MEMORY_PROVIDER: str = "chromadb"
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
    PINECONE_INDEX_NAME: str = ""

    # Pagamentos
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # Observabilidade
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    SENTRY_DSN: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@saas-financeiro.com"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def database_url_sync(self) -> str:
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY deve ter pelo menos 32 caracteres. "
                "Gere uma com: openssl rand -hex 32"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única de configurações (padrão Singleton)."""
    return Settings()


settings = get_settings()
