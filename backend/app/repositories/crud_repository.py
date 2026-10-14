from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class CrudRepository(Generic[ModelT]):
    """Accès générique aux entités persistées."""

    def __init__(self, db: Session, model: type[ModelT]) -> None:
        self.db = db
        self.model = model

    def get(self, entity_id: UUID) -> ModelT | None:
        return self.db.get(self.model, entity_id)

    def list(self, *conditions: Any) -> Sequence[ModelT]:
        return self.db.scalars(select(self.model).where(*conditions)).all()

    def create(self, **values: Any) -> ModelT:
        entity = self.model(**values)
        self.db.add(entity)
        self.db.flush()
        return entity

    def update(self, entity: ModelT, **values: Any) -> ModelT:
        for key, value in values.items():
            setattr(entity, key, value)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.flush()
