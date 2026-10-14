from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base des modèles SQLAlchemy."""


def get_db() -> Generator[Session, None, None]:
    """Fournit une session de base de données."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
