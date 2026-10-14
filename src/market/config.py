from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_path: str = "artifacts/model_v1.0.joblib"
    model_name: str | None = None
    model_alias: str = "test"
    mlflow_tracking_uri: str = "http://127.0.0.1:5000"
    # db_url: str | None = "postgresql+asyncpg://postgres:admin@localhost:5432/postgres"
    db_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DB_URL", "DATABASE_URL"),
    )
    db_echo: bool = False
    log_level: str = "INFO"
    service_version: str = "0.1"

    model_config = {"env_file": ".env", "protected_namespaces": ()}

settings = Settings()