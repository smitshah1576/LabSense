"""Configuration settings for LabSense backend."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    DATABASE_URL: str = "postgresql://labsense:labsense_dev@localhost:5432/labsense"
    JWT_SECRET: str = "labsense-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    TCP_HOST: str = "0.0.0.0"
    TCP_PORT: int = 9000
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    HEARTBEAT_TIMEOUT_SECONDS: int = 15
    IDLE_THRESHOLD_SECONDS: int = 300
    CPU_THRESHOLD_PERCENT: float = 5.0

    model_config = SettingsConfigDict(
        env_prefix="LABSENSE_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
