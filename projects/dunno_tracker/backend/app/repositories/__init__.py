from app.repositories.base import BaseRepository

_repo: BaseRepository | None = None


def get_repo() -> BaseRepository:
    global _repo
    if _repo is None:
        from app.config import settings
        if settings.db_type == "postgres":
            from app.repositories.postgres_repo import PostgresRepository
            _repo = PostgresRepository(settings.postgres_url)
        elif settings.db_type == "clickhouse":
            from app.repositories.clickhouse_repo import ClickHouseRepository
            _repo = ClickHouseRepository(
                postgres_dsn=settings.postgres_url,
                ch_host=settings.clickhouse_host,
                ch_port=settings.clickhouse_port,
                ch_user=settings.clickhouse_user,
                ch_password=settings.clickhouse_password,
                ch_database=settings.clickhouse_database,
            )
        else:  # supabase (default)
            from app.repositories.supabase_repo import SupabaseRepository
            _repo = SupabaseRepository(settings.supabase_url, settings.service_key)
    return _repo
