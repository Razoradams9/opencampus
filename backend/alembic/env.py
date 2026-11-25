import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers models on the metadata)
from app.core.config import ConfigError, load_env_file
from app.db.base import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def migration_url() -> str:
    # Tests pass an explicit URL; otherwise use the owner-role URL from the env.
    url = config.attributes.get("url")
    if url:
        return url
    load_env_file()
    url = os.getenv("OPENCAMPUS_MIGRATION_DATABASE_URL")
    if not url:
        raise ConfigError("OPENCAMPUS_MIGRATION_DATABASE_URL must be set to run migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(url=migration_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(migration_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
