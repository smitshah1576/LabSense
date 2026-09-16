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
    # Browsers opening the dashboard by LAN IP send that origin, not
    # "localhost", so every host the dashboard is reached from must be listed.
    # Override via LABSENSE_CORS_ORIGINS in .env (JSON list).
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    HEARTBEAT_TIMEOUT_SECONDS: int = 15
    IDLE_THRESHOLD_SECONDS: int = 300
    CPU_THRESHOLD_PERCENT: float = 5.0
    # Lab operating hours and timetable slots are stored as local wall-clock
    # times, so lab state must be computed against this zone — not UTC.
    TIMEZONE: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(
        env_prefix="LABSENSE_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
