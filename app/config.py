from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://agentgate:agentgate@localhost:5432/agentgate"
    db_echo: bool = False
    app_env: str = "development"

    # Connection pool — override via env vars for production tuning
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
