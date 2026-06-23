"""
SQLAlchemy database engine and session configuration.
Uses SQLite for zero-config persistent storage.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Store the database file in the project root directory
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SQLITE_URL = f"sqlite:///{os.path.join(DB_DIR, 'solarshield.db')}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup."""
    from backend.app.models import EdgeNode, Alert, TelemetryLog, FaceProfile, Notification  # noqa: F401
    Base.metadata.create_all(bind=engine)
