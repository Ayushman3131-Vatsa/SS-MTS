from functools import lru_cache
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


BACKEND_DIRECTORY = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIRECTORY / ".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:admin@localhost:5432/multi_tenant_poc"
    migration_database_url: str | None = None

    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    environment: str = "development"

    # Comma-separated browser origins allowed to call the API directly.
    # Leave empty when a same-origin proxy exposes the API under /api.
    cors_allowed_origins: str = ""

    browser_session_expire_minutes: int = Field(default=60, ge=1, le=1440)
    session_cookie_name: str = Field(
        default="mt_session",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    csrf_cookie_name: str = Field(
        default="mt_csrf",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    auth_rate_limit_window_minutes: int = Field(default=15, ge=1, le=60)
    auth_account_failure_limit: int = Field(default=5, ge=1, le=100)
    auth_ip_failure_limit: int = Field(default=20, ge=1, le=1000)
    auth_lockout_minutes: int = Field(default=15, ge=1, le=1440)

    max_request_body_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    deactivated_offering_retention_days: int = Field(default=90, ge=1, le=3650)
    smartskale_setup_email: str = Field(default="hrms.support@smartskale.com")
    attachment_storage_root: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "multi_tenant_poc_attachments"
    )
    attachment_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    attachment_max_per_task: int = Field(default=20, ge=1, le=100)
    attachment_allowed_media_types: str = (
        "image/png,image/jpeg,image/webp,application/pdf,text/plain,text/csv,"
        "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Google SMTP Integration Settings
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: str | None = Field(default="hrms.smartskale@gmail.com")
    smtp_password: str | None = Field(default=None)
    smtp_from_email: str | None = Field(default="hrms.smartskale@gmail.com")
    smtp_from_name: str = Field(default="SmartSkale HRMS")
    smtp_use_tls: bool = Field(default=True)
    smtp_timeout_seconds: int = Field(default=10, ge=1, le=60)
    smtp_enabled: bool = Field(default=True)

    @property
    def is_development(self) -> bool:
        return self.environment.strip().lower() in {
            "dev",
            "development",
            "local",
            "test",
            "testing",
        }

    @property
    def secure_cookies(self) -> bool:
        return not self.is_development

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin
            for origin in self.cors_allowed_origins.split(",")
            if origin
        ]

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_cors_allowed_origins(cls, value: str) -> str:
        normalized: list[str] = []
        for candidate in value.split(","):
            origin = candidate.strip().rstrip("/")
            if not origin:
                continue
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(
                    "CORS_ALLOWED_ORIGINS must contain comma-separated HTTP(S) "
                    "origins without paths, credentials, queries, fragments, or wildcards"
                )
            if origin not in normalized:
                normalized.append(origin)
        return ",".join(normalized)

    @field_validator("smartskale_setup_email")
    @classmethod
    def normalize_setup_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("SMARTSKALE_SETUP_EMAIL must be a valid email address")
        return email

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.session_cookie_name == self.csrf_cookie_name:
            raise ValueError("SESSION_COOKIE_NAME and CSRF_COOKIE_NAME must be different")
        if not self.is_development and (
            self.jwt_secret_key == "change-me-to-a-long-random-string"
            or len(self.jwt_secret_key) < 32
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be a unique secret of at least 32 characters "
                "outside development and test environments"
            )
        if not self.is_development:
            if not self.migration_database_url:
                raise ValueError("MIGRATION_DATABASE_URL is required outside development and test")
            runtime_url = make_url(self.database_url)
            migration_url = make_url(self.migration_database_url)
            if (
                self.migration_database_url == self.database_url
                or runtime_url.username == migration_url.username
            ):
                raise ValueError(
                    "MIGRATION_DATABASE_URL must use a different privileged role than DATABASE_URL"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
