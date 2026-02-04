"""
User List CRUD Manager.

Provides async CRUD operations for UserList and UserListMember models.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.user_lists import UserList, UserListCreate, UserListMember
from shared.services.database.core.base_crud import BaseCRUDManager


class UserListCRUDManager(BaseCRUDManager):
    """
    CRUD manager for UserList operations.
    """

    def __init__(self, model=None):
        self.model = model or UserList

    async def create_user_list(
        self, list_data: UserListCreate, session: AsyncSession
    ) -> UserList:
        """Create a new user list."""
        user_list = UserList(
            name=list_data.name,
            description=list_data.description,
            slack_id=f"UL-{list_data.name[:10]}",
        )
        session.add(user_list)
        try:
            await session.commit()
            await session.refresh(user_list)
            return user_list
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error creating user list: {e}")

    async def get_user_list_by_name(
        self, name: str, session: AsyncSession
    ) -> Optional[UserList]:
        """Get a user list by name."""
        query = select(UserList).filter(UserList.name == name)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_user_lists(self, session: AsyncSession) -> List[UserList]:
        """Get all user lists."""
        query = select(UserList)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def add_member(
        self, list_id: int, slack_id: str, user_name: str, session: AsyncSession
    ) -> UserListMember:
        """Add a user to a user list."""
        member = UserListMember(
            user_list_id=list_id,
            slack_id=slack_id,
            user_name=user_name,
        )
        session.add(member)
        try:
            await session.commit()
            await session.refresh(member)
            return member
        except Exception as e:
            # Check for unique constraint violation manually if needed, or let it raise
            await session.rollback()
            raise Exception(f"Error adding member: {e}")


# Singleton instance
user_list_manager = UserListCRUDManager()
