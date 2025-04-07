import os
import platform
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import enum

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
        print(f"Database '{db_path}' already exists.")
        return

    app_data_location.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    print(f"Database '{db_path}' created successfully.")


class SessionContext:
    def __init__(self):
        self.session = None
    
    def __enter__(self):
        self.session = SessionFactory()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()
