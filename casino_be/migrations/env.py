from __future__ import with_statement

import sys # Import sys
import os # Import os
from os.path import abspath, dirname # Import abspath and dirname

# Add the parent directory of 'migrations' (i.e., 'casino_be') to sys.path
# This allows 'from models import db' to work correctly.
sys.path.insert(0, dirname(dirname(abspath(__file__))))

import logging
from logging.config import fileConfig

from flask import current_app
from sqlalchemy import engine_from_config, pool # Import necessary components
from sqlalchemy import MetaData # Import MetaData

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None: # Check if config file name is set
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# --- Manually set target metadata ---
# Import your models base or individual models
# Option 1: Import Base from your models file if you have one
# from models import Base
# target_metadata = Base.metadata

# Option 2: Import the db object from your Flask app setup
# This requires the Flask app context to be available, which might be complex outside the app
# from app import db # Assuming 'db = SQLAlchemy()' in your app.py
# target_metadata = db.metadata

# Option 3: Import all models and use a shared MetaData instance
# Ensure all your models use the same MetaData object (SQLAlchemy() usually handles this)
from models import db # If db = SQLAlchemy() is defined in models.py
target_metadata = db.metadata
# --- End Metadata Setup ---


# --- Configure Database URL ---
# Use the database URL from Flask app config if possible, otherwise from alembic.ini
flask_app_config_url = None
try:
    # This relies on Flask context being available, which might not always be the case
    # especially during offline migrations or initial setup.
    # Consider setting SQLALCHEMY_URL directly in alembic.ini as a fallback.
    flask_app_config_url = current_app.config['SQLALCHEMY_DATABASE_URI']
except RuntimeError: # No app context
    logger.warning("Flask app context not available. Trying alembic.ini for database URL.")
    flask_app_config_url = None

# Get URL from alembic.ini section [alembic] key 'sqlalchemy.url'
ini_url = config.get_main_option("sqlalchemy.url")

if flask_app_config_url:
    config.set_main_option('sqlalchemy.url', flask_app_config_url)
    logger.info(f"Using database URL from Flask config: {flask_app_config_url}")
elif ini_url:
    # URL is already set from ini file, no need to set it again
    logger.info(f"Using database URL from alembic.ini: {ini_url}")
else:
    logger.warning("Database URL not found in Flask config or alembic.ini. Defaulting to SQLite for migration generation.")
    # Optionally, raise an error or exit
    # raise ValueError("Missing database URL configuration for Alembic.")
    config.set_main_option('sqlalchemy.url', 'sqlite:///./_alembic_dummy.db')


# --- Rest of the env.py (mostly standard) ---

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"}, # Add dialect opts if needed
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use configuration from alembic.ini for the engine
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
             # compare_type=True # Enable type comparison if needed
        )

        with context.begin_transaction():
            context.run_migrations()

# this callback is used to prevent an auto-migration from being generated
# when there are no changes to the schema
# reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
def process_revision_directives(context, revision, directives):
    if config.cmd_opts.autogenerate: # Check attribute exists
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            logger.info('No changes in schema detected.')


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

