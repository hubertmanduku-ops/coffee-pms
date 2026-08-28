import os


class Settings:
    """Simple environment-driven settings (no extra deps)."""

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/coffee_pms"
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-in-production")
    SESSION_COOKIE_NAME: str = "cpms_session"
    SESSION_MAX_AGE: int = 60 * 60 * 12  # 12 hours
    APP_NAME: str = "Coffee Pulping Management System"
    ENV: str = os.getenv("ENV", "development")


settings = Settings()

# Railway/Heroku-style DATABASE_URL sometimes starts with postgres:// — normalize to the
# psycopg2 dialect SQLAlchemy expects.
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace(
        "postgres://", "postgresql+psycopg2://", 1
    )
elif settings.DATABASE_URL.startswith("postgresql://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )
