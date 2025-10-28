import logging
import ctypes

from contextlib import contextmanager
import os
import platform
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from build_bridge.utils.paths import get_resource_path


Base = declarative_base()

# Check for an environment variable for the database path
env_db_path = os.getenv('BUILD_BRIDGE_DB_PATH')

if env_db_path:
    db_path = Path(env_db_path)
else:
    # Determine the application data directory based on the operating system using pathlib
    if platform.system() == 'Windows':
        app_data_location = Path(os.getenv('APPDATA')) / 'BuildBridge'
    elif platform.system() == 'Darwin':  # macOS
        app_data_location = Path.home() / 'Library' / 'Application Support' / 'BuildBridge'
    else:  # Linux and other Unix-like systems
        app_data_location = Path.home() / '.local' / 'share' / 'BuildBridge'

    db_path = app_data_location / 'build_bridge.db'


DATABASE_URL = f'sqlite:///{db_path}'
engine = create_engine(DATABASE_URL)

SessionFactory = sessionmaker(bind=engine)

def ensure_database_integrity(engine, alembic_cfg):
    with engine.connect() as conn:
        inspector = inspect(conn)
        has_version_table = inspector.has_table("alembic_version")

        existing_tables = set(inspector.get_table_names())

        if not existing_tables:
            logging.info("Database empty, running full upgrade.")
            command.upgrade(alembic_cfg, "head")
            return

        # If the only existing table is alembic version, we need to run migrations
        if has_version_table and existing_tables == {"alembic_version"}:
            logging.warning("Database appears stamped but missing schema — repairing.")
            conn.execute(text("DROP TABLE alembic_version"))
            conn.commit()
            command.upgrade(alembic_cfg, "head")
            return

        logging.info("Upgrading database to latest revision.")
        command.upgrade(alembic_cfg, "head")


def init_database(engine, alembic_cfg):
    """Create or validate the database before migrations."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        logging.info(f"New database will be created at {db_path}")
        command.upgrade(alembic_cfg, "head")
        logging.info("Database created and migrated to head.")
        return

    # Existing DB, verify and repair if needed. This is mostly
    # because of v 0.6.0/0.6.1 where I stamped the db when it was
    # empty and if someone has a db stamped like that, migrations will
    # never run! But it's good to check integrity anyways.
    logging.info("Validating existing database integrity...")
    ensure_database_integrity(engine, alembic_cfg)
    logging.info("Database integrity verified.")

def run_pending_migrations(alembic_cfg):
    """Upgrade database if not already at latest revision."""
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext

    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()

        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()

        if current_rev != head_rev:
            logging.info(f"Upgrading DB from {current_rev or 'base'} -> {head_rev}")
            command.upgrade(alembic_cfg, "head")
        else:
            logging.info("Database already at latest revision.")

def create_or_update_db():
    migrations_dir = get_resource_path("alembic")
    alembic_ini_path = get_resource_path("alembic.ini")

    if not os.path.exists(migrations_dir) or not os.path.exists(alembic_ini_path):
        logging.critical(f"Alembic config or migration folder missing. "
                         f"Expected dir:{migrations_dir}, ini:{alembic_ini_path}")
        raise FileNotFoundError("Alembic migration resources not found.")

    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    try:
        init_database(engine, alembic_cfg)
        run_pending_migrations(alembic_cfg)
        logging.info("Database initialization and migration completed successfully.")
    except Exception:
        logging.exception("Database migration failed")
        raise


@contextmanager
def session_scope(commit_on_success=True): # Added flag
    """Provide a transactional scope around a series of operations.
       Commit is optional on successful completion of the block.
    """
    session = SessionFactory()
    success = False
    try:
        yield session
        success = True # Mark as success only if yield completes without error
    except Exception:
        session.rollback()
        raise
    finally:
        if success and commit_on_success:
            try:
                session.commit()
            except Exception:
                session.rollback()
                raise
        session.close()