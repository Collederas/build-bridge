from contextlib import contextmanager
import os
import platform
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

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
        # os.remove(db_path)
        print(f"Database '{db_path}' already exists.")
        return
    
    app_data_location.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    print(f"Database '{db_path}' created successfully.")


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
                # print("Commit failed, rolling back.") # Optional debug
                session.rollback()
                raise # Re-raise the exception during commit
        # If 'success' is False, rollback already happened in the 'except' block.
        # If 'commit_on_success' is False, we intentionally skip commit.
        # print("Closing session.") # Optional debug
        session.close()