"""
User List CRUD Manager.

Provides async CRUD operations for UserList and UserListMember models.
"""

from typing import List, Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.user_lists import UserList, UserListCreate, UserListMember
from shared.services.database.core.base_crud import BaseCRUDManager


class UserListCRUDManager(BaseCRUDManager):
    """
    CRUD manager for UserList operations.
    """

    def __init__(self, model=None):
        self.model = model or UserList

    async def fix_sequences(self, session: AsyncSession) -> None:
        """Sync PostgreSQL sequences with the maximum ID in the tables."""
        tables = ["user_lists", "user_list_members"]
        for table in tables:
            try:
                # Use setval to sync sequence with current max ID
                await session.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 0) + 1, false) FROM {table}"
                    )
                )
            except Exception as e:
                print(f"[WARNING] Failed to sync sequence for {table}: {e}")
        await session.commit()

    async def create_user_list(
        self, list_data: UserListCreate, session: AsyncSession
    ) -> UserList:
        """Create a new user list with retry logic for sequence sync."""
        user_list = UserList(
            name=list_data.name,
            description=list_data.description,
            slack_id=f"UL-{list_data.name[:10]}",
        )

        try:
            session.add(user_list)
            await session.commit()
            await session.refresh(user_list)
            return user_list
        except IntegrityError:
            await session.rollback()
            print("[INFO] Unique violation detected, attempting sequence sync...")
            await self.fix_sequences(session)

            # Retry once
            try:
                # Need to recreate the object because the previous one is tied to the failed transaction
                user_list_retry = UserList(
                    name=list_data.name,
                    description=list_data.description,
                    slack_id=f"UL-{list_data.name[:10]}",
                )
                session.add(user_list_retry)
                await session.commit()
                await session.refresh(user_list_retry)
                return user_list_retry
            except Exception as retry_e:
                await session.rollback()
                raise Exception(
                    f"Error creating user list after sequence sync: {retry_e}"
                )
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

    async def get_user_list_by_id(
        self, list_id: int, session: AsyncSession
    ) -> Optional[UserList]:
        """Get a user list by ID with members loaded."""
        from sqlalchemy.orm import selectinload

        query = (
            select(UserList)
            .options(selectinload(UserList.members))
            .filter(UserList.id == list_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_list_members(
        self, list_id: int, session: AsyncSession
    ) -> List[UserListMember]:
        """Get all members of a user list."""
        query = select(UserListMember).filter(UserListMember.user_list_id == list_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_list_member_slack_ids(
        self, list_id: int, session: AsyncSession
    ) -> List[str]:
        """Get all member slack_ids of a user list."""
        members = await self.get_list_members(list_id, session)
        return [m.slack_id for m in members]

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

    async def update_list_members(
        self,
        list_id: int,
        slack_ids: List[str],
        user_names: List[str],
        session: AsyncSession,
    ) -> None:
        """Replace all members of a list with new slack IDs."""
        from sqlalchemy import delete

        try:
            # Remove existing members
            await session.execute(
                delete(UserListMember).where(UserListMember.user_list_id == list_id)
            )
            await session.commit()

            # Add new members
            for slack_id, user_name in zip(slack_ids, user_names):
                member = UserListMember(
                    user_list_id=list_id,
                    slack_id=slack_id,
                    user_name=user_name,
                )
                session.add(member)
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error updating list members: {e}")

    async def remove_members(
        self, list_id: int, slack_ids: List[str], session: AsyncSession
    ) -> None:
        """Remove specific users from a list by their slack_ids."""
        from sqlalchemy import and_, delete

        try:
            await session.execute(
                delete(UserListMember).where(
                    and_(
                        UserListMember.user_list_id == list_id,
                        UserListMember.slack_id.in_(slack_ids),
                    )
                )
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error removing members: {e}")


# Singleton instance
user_list_manager = UserListCRUDManager()
