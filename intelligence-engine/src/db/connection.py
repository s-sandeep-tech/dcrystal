from contextlib import contextmanager
from contextvars import ContextVar
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from ..config import settings
from ..utils.logger import logger
from .models import Base

# Standalone SQLAlchemy engine
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_task_session = ContextVar("intelligence_task_session", default=None)


@contextmanager
def task_transaction():
    """Share one transaction across nested output writers and the task receipt."""
    with get_db_session() as session:
        token = _task_session.set(session)
        try:
            yield session
        finally:
            _task_session.reset(token)

def init_db():
    """Initializes exclusive IntelligenceEngine tables in the database."""
    try:
        logger.info("Initializing exclusive IntelligenceEngine database tables...")
        # create_all only creates tables defined in Base.metadata that do NOT already exist
        Base.metadata.create_all(bind=engine)
        logger.info("IntelligenceEngine database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
        raise

@contextmanager
def get_db_session():
    """Context manager for safe SQLAlchemy database session lifecycle."""
    active = _task_session.get()
    if active is not None:
        yield active
        return
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def check_db_health() -> bool:
    """Performs a simple healthcheck query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return False
