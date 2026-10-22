import os
from pathlib import Path
from typing import Optional

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        # Redis configuration
        REDIS_HOST: str = "redis"
        REDIS_PORT: int = 6379
        REDIS_DB: int = 0
        REDIS_PASSWORD: Optional[str] = None
        REDIS_QUEUE_NAME: str = "intelligence_queue"
        REDIS_RESULT_PREFIX: str = "intelligence:task:"
        REDIS_EVENT_CHANNEL: str = "intelligence:events"
        REDIS_TASK_TTL_SECONDS: int = 86400  # 24 hours retention
        REDIS_TASK_LEASE_SECONDS: int = 120
        REDIS_TASK_MAX_ATTEMPTS: int = 3

        # Database configuration (PostgreSQL)
        SQLALCHEMY_DATABASE_URI: str = "postgresql+psycopg2://meetaccess:meetpass@db:5432/dcrystaldb"
        DB_POOL_SIZE: int = 5
        DB_MAX_OVERFLOW: int = 10
        DB_POOL_TIMEOUT: int = 30
        DB_POOL_RECYCLE: int = 1800

        # Gemini configuration (Exclusive to IntelligenceEngine)
        INTELLIGENCE_GEMINI_API_KEY: Optional[str] = None
        GEMINI_API_KEY: Optional[str] = None
        GEMINI_MODEL: str = "gemini-3.5-flash-lite"

        @property
        def active_gemini_api_key(self) -> Optional[str]:
            return self.INTELLIGENCE_GEMINI_API_KEY or self.GEMINI_API_KEY

        # Application settings
        LOG_LEVEL: str = "INFO"
        APP_ENV: str = "production"
        MODEL_STORE_DIR: str = str(Path(__file__).resolve().parents[1] / "model_store")

        model_config = SettingsConfigDict(
            env_file=(".env", "../.env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )

    settings = Settings()

except ImportError:
    # Graceful fallback when running in lightweight environments without pydantic-settings
    class LightweightSettings:
        REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
        REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
        REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
        REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
        REDIS_QUEUE_NAME: str = os.getenv("REDIS_QUEUE_NAME", "intelligence_queue")
        REDIS_RESULT_PREFIX: str = os.getenv("REDIS_RESULT_PREFIX", "intelligence:task:")
        REDIS_EVENT_CHANNEL: str = os.getenv("REDIS_EVENT_CHANNEL", "intelligence:events")
        REDIS_TASK_TTL_SECONDS: int = int(os.getenv("REDIS_TASK_TTL_SECONDS", "86400"))
        REDIS_TASK_LEASE_SECONDS: int = int(os.getenv("REDIS_TASK_LEASE_SECONDS", "120"))
        REDIS_TASK_MAX_ATTEMPTS: int = int(os.getenv("REDIS_TASK_MAX_ATTEMPTS", "3"))

        SQLALCHEMY_DATABASE_URI: str = os.getenv(
            "SQLALCHEMY_DATABASE_URI",
            "postgresql+psycopg2://meetaccess:meetpass@localhost:5433/dcrystaldb"
        )
        DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
        DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

        INTELLIGENCE_GEMINI_API_KEY: Optional[str] = os.getenv("INTELLIGENCE_GEMINI_API_KEY")
        GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
        GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

        @property
        def active_gemini_api_key(self) -> Optional[str]:
            return self.INTELLIGENCE_GEMINI_API_KEY or self.GEMINI_API_KEY


        LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
        APP_ENV: str = os.getenv("APP_ENV", "production")
        MODEL_STORE_DIR: str = os.getenv("MODEL_STORE_DIR", str(Path(__file__).resolve().parents[1] / "model_store"))

    settings = LightweightSettings()

