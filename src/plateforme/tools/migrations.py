# plateforme.tools.migrations
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database migrations using Alembic
within the Plateforme framework.
"""

from logging.config import fileConfig

from alembic import context

from plateforme.core.database.engines import engine_from_config
from plateforme.core.database.pool import NullPool
from plateforme.core.database.schema import MetaData

# Declare the Alembic configuration object, which provides access to the values
# within the ".ini" file in use.
config = context.config

# Interpret the configuration file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add model's "MetaData" object here for "autogenerate" support.
# FIXME: from myapp import mymodel
# FIXME: target_metadata = mymodel.Base.metadata
target_metadata: MetaData | None = None

# Other values from the config, defined by the needs of "env.py", can be also
# acquired:
# FIXME: my_important_option = config.get_main_option("my_important_option")
# FIXME: ... etc.


def run_migrations_offline() -> None:
    """
    Run migrations in `offline` mode.

    This configures the context with just a URL and not an engine, though an
    engine is acceptable here as well. By skipping the engine creation we don't
    even need a DBAPI to be available.

    Calls to `context.execute()` here emit the given string to the script
    output.
    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in `online` mode.

    In this scenario we need to create an engine and associate a connection
    with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
