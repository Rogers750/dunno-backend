from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB backend selector: supabase | postgres | clickhouse
    db_type: str = "supabase"

    # Supabase
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_key: str = ""

    # Postgres (used by db_type=postgres and as relational store for db_type=clickhouse)
    postgres_url: str = ""

    # ClickHouse (used by db_type=clickhouse)
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "dunno"

    # LLM for analysis — set exactly one; priority: anthropic > openai > deepseek > gemini
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""

    secret_key: str = "change-me-in-production"
    environment: str = "development"
    allowed_origins: str = "http://localhost:8081,http://localhost:3000"

    @property
    def service_key(self) -> str:
        return self.supabase_service_key or self.supabase_key

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
