"""
Database module - SQLAlchemy setup and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Base class for all models
Base = declarative_base()

# Create engine based on environment
if settings.database_url.startswith("sqlite"):
    # SQLite - use StaticPool for threading
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.debug,  # Log SQL queries if debug=True
    )
else:
    # PostgreSQL or other
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,  # Test connections before using
        echo=settings.debug,
    )

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Session:
    """
    Dependency for FastAPI - provides database session
    Usage in endpoint:
        def get_data(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    Call this once when app starts
    """
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized successfully")


def drop_all_tables():
    """
    Drop all tables - WARNING: This deletes all data!
    Use only in development/testing
    """
    Base.metadata.drop_all(bind=engine)
    logger.warning("⚠️ All database tables dropped")


if __name__ == "__main__":
    # For testing - initialize database
    print("Initializing database...")
    init_db()
    print("✅ Done!")
