import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.common.config import get_settings
from app.common.db.base import Base
from app.db.all_models import *  # noqa: F401,F403  (registers all tables on Base.metadata)

config = context.config
_settings = get_settings()
config.set_main_option(
    "sqlalchemy.url",
    _settings.migration_database_url or _settings.database_url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        # The owner is subject to FORCE RLS. Set platform scope only inside
        # Alembic's managed transaction. Executing this before
        # begin_transaction() triggers SQLAlchemy autobegin and causes the
        # connection context to roll the migration back on exit.
        connection.execute(text("SELECT set_config('app.principal_type', 'admin', true)"))
        connection.execute(text("SELECT set_config('app.tenant_id', '', true)"))
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
