from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ==========================================
    # APP
    # ==========================================
    APP_NAME: str = "SaaS Financeiro"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    API_V1_STR: str = "/api/v1"
    APP_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:3000"

    # ==========================================
    # SECURITY
    # ==========================================
    # Generate with: openssl rand -hex 32
    SECRET_KEY: str = "dev-secret-key-replace-before-production-deployment"
    JWT_ALGORITHM: str = "HS256"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str, info) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ==========================================
    # DATABASE
    # ==========================================
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "saas_user"
    POSTGRES_PASSWORD: str = "dev_password_123"
    POSTGRES_DB: str = "saas_financeiro"

    DATABASE_URL: str = (
        "postgresql+psycopg://saas_user:dev_password_123@localhost:5432/saas_financeiro"
    )

    @computed_field
    @property
    def database_url_sync(self) -> str:
        """Sync URL for Alembic (psycopg3). Runtime uses asyncpg via session.py."""
        return self.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg://"
        )

    # ==========================================
    # REDIS
    # ==========================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    REDIS_URL: str = "redis://localhost:6379/0"

    CACHE_TTL: int = 300

    # ==========================================
    # CELERY
    # ==========================================
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ==========================================
    # AI
    # ==========================================
    AI_PROVIDER: str = "openai"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-5"

    AI_TEMPERATURE: float = 0.3

    # ==========================================
    # AUDIO
    # ==========================================
    WHISPER_MODEL: str = "whisper-1"

    TTS_PROVIDER: str = "openai"
    TTS_VOICE: str = "nova"

    # ==========================================
    # WHATSAPP
    # ==========================================
    # Temporary: "evolution" while Meta account is unverified (error 130497).
    # Switch back to "cloud_api" after completing Meta business verification.
    # See WHATSAPP_MIGRATION.md for the full migration plan.
    WHATSAPP_PROVIDER: str = "evolution"

    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_TEST_NUMBER: str = ""

    WHATSAPP_VERIFY_TOKEN: str = "meu_token_secreto_de_verificacao"

    WHATSAPP_API_VERSION: str = "v21.0"

    # ── Evolution API (active provider) ───────────────────────────────────
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = "minha-chave-evolution-123"
    EVOLUTION_INSTANCE: str = "saas-financeiro"

    # ==========================================
    # STORAGE
    # ==========================================
    STORAGE_PROVIDER: str = "minio"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"

    MINIO_BUCKET: str = "saas-files"
    MINIO_USE_SSL: bool = False

    AWS_REGION: str = "us-east-1"

    # ==========================================
    # MEMORY / VECTOR DB
    # ==========================================
    MEMORY_PROVIDER: str = "chromadb"

    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8000

    # ==========================================
    # LOGGING
    # ==========================================
    LOG_LEVEL: str = "INFO"

    # ==========================================
    # RATE LIMIT
    # ==========================================
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # ==========================================
    # EMAIL
    # ==========================================
    SMTP_PORT: int = 587
    SMTP_FROM_EMAIL: str = "noreply@saas-financeiro.com"

    # ==========================================
    # CORS
    # ==========================================
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
