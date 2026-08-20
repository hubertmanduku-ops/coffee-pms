import os

from dotenv import load_dotenv

load_dotenv()  # reads a .env file in the project root into the process environment, if present


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
    # Password used for the seeded admin account on first startup only (when no users exist yet).
    # Override this in production (e.g. set it in Railway's Variables tab) instead of using the
    # insecure default — then log in and either change it via a new admin user, or rotate it again.
    ADMIN_SEED_PASSWORD: str = os.getenv("ADMIN_SEED_PASSWORD", "admin123")


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

if settings.ENV == "production" and settings.SECRET_KEY == "change-this-secret-in-production":
    import warnings

    warnings.warn(
        "SECRET_KEY is still the insecure default in a production environment. "
        "Set a random SECRET_KEY environment variable.",
        stacklevel=1,
    )
