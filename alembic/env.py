
"""
Async Alembic environment. Uses the app's own settings so migrations
always target the same database the app connects to, and autogenerate
sees every model via app.models.__init__.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401 - populates Base.metadata

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Build a sync URL for Alembic (remove +asyncpg if present)
sync_url = settings.database_url
if "+asyncpg" in sync_url:
    sync_url = sync_url.replace("+asyncpg", "")

config.set_main_option("sqlalchemy.url", sync_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL script."""
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
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a sync engine."""
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

