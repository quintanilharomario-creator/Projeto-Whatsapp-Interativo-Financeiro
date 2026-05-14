from pydantic import computed_field
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
    SECRET_KEY: str = "super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"

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
    WHATSAPP_PROVIDER: str = "cloud_api"

    WHATSAPP_VERIFY_TOKEN: str = (
        "meu_token_secreto_de_verificacao"
    )

    WHATSAPP_API_VERSION: str = "v21.0"

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

