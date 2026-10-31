import sys
from logging.config import fileConfig
from os.path import abspath, dirname

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure backend root is on sys.path
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# Register every module's tables on the shared Base.metadata:
import app.models  # noqa: E402,F401  — P2 catalog tables
import app.modules.billing.models  # noqa: E402,F401  — P4 billing tables

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,  # SQLite needs batch ALTER TABLE
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
