import logging

from contextlib import contextmanager
import os
import platform
import sys
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect
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

def initialize_database():
    if db_path.exists():
        logging.info(f"Database '{db_path}' already exists.")
        return
    
    app_data_location.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    logging.info(f"Database '{db_path}' created successfully.")

def run_migrations():
    initialize_database()
    migrations_dir = get_resource_path("alembic")
    alembic_ini_path = get_resource_path("alembic.ini")

    if not os.path.exists(migrations_dir) or not os.path.exists(alembic_ini_path):
        logging.info(f"Migration folders don't exist: {migrations_dir}")
        sys.exit(1)

    alembic_cfg = Config(alembic_ini_path)
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)

    needs_stamp = False
    if not os.path.exists(db_path):
        logging.info("Database does not exist. Creating and stamping initial schema.")
        engine = create_engine(DATABASE_URL)
        engine.connect().close()
        needs_stamp = True

    else:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as connection:
               inspector = inspect(engine)
               if not inspector.has_table("alembic_version"):
                   logging.info("Existing DB found, but no alembic version table. Stamping current.")
                   needs_stamp = True
        except Exception as e:
            logging.info(f"Error inspecting existing database: {e}. Handle corruption/backup.")
            sys.exit(1)

    try:
        logging.info("Running Alembic upgrades...")
        command.upgrade(alembic_cfg, "head")
        logging.info("Alembic upgrades completed.")

        if needs_stamp:
             logging.info("Stamping database to current head revision...")
             command.stamp(alembic_cfg, "head")
             logging.info("Database stamped.")
    except Exception as e:
        logging.info(e)
        sys.exit(1)


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