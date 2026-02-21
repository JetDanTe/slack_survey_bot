from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from shared.schemas.base_models import Base


class BaseCRUDManager(ABC):
    model: type[Base] = None

    @abstractmethod
    def __init__(self, model: type[Base]):
        pass

    async def create(self, *, session: AsyncSession, **kwargs) -> Optional[Base]:
        instance = self.model(**kwargs)
        session.add(instance)
        try:
            await session.commit()
            return instance
        except Exception:
            await session.rollback()
            raise Exception(
                "Error has occurred while creating {self.model} instance with {kwargs}, {e}"
            )

    async def get(
        self, *, session: AsyncSession, field_value: Any, field: InstrumentedAttribute
    ) -> Optional[Base]:
        result = select(self.model).filter(field == field_value)
        instance = await session.execute(result)
        return instance.scalar_one_or_none()

    async def get_all(self, session: AsyncSession, model=None):
        model = model or self.model
        query = select(model)
        result = await session.execute(query)
        return result.scalars().all()

    async def update(self, session: AsyncSession, instance: Base, **kwargs) -> Base:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        session.add(instance)
        try:
            await session.commit()
            await session.refresh(instance)
            return instance
        except Exception:
            await session.rollback()
            raise Exception(
                f"Error has occurred while updating {self.model} instance with {kwargs}"
            )
