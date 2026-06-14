from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres connection string. Provide via .env (see .env.example).
    database_url: str = "postgresql+psycopg2://USER:PASSWORD@localhost:5432/receipts"

    upload_dir: str = "uploads"
    frontend_origin: str = "http://localhost:5173"

    # Optional explicit path to the tesseract binary.
    tesseract_cmd: str | None = None

    # SeaweedFS filer base URL (no trailing slash).
    seaweedfs_filer_url: str = "http://localhost:8888"

    # --- Auth ---
    # Secret used to sign JWTs. MUST be overridden in .env for any real use.
    secret_key: str = "CHANGE_ME_dev_only_insecure_secret"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # Seed super-admin credentials (used by `python -m app.seed`).
    superadmin_email: str = "admin@example.com"
    superadmin_password: str = "changeme"
    superadmin_name: str = "Super Admin"

    # --- Email (weekly digest). Sending is a no-op until smtp_host is set. ---
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "Receipt Scanner <no-reply@receiptscanner.local>"
    smtp_use_tls: bool = True  # STARTTLS
    app_base_url: str = "http://localhost:5173"  # used for links in emails


settings = Settings()
