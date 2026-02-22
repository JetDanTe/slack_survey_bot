from typing import List

from shared.schemas.user_lists import UserList, UserListCreate
from shared.services.database.core.session import async_session_maker
from shared.services.database.user_lists.crud import user_list_manager


class UsersListsHandler:
    async def get_all_surveys(self) -> list[UserList]:
        async with async_session_maker() as session:
            surveys = await user_list_manager.get_all_user_lists(session=session)
            return surveys

    async def create_user_list(self, name: str, description: str = "") -> UserList:
        """Create a new user list."""
        async with async_session_maker() as session:
            list_data = UserListCreate(name=name, description=description)
            return await user_list_manager.create_user_list(list_data, session)

    async def get_user_list_with_members(self, list_id: int) -> UserList | None:
        """Get a user list with its members loaded."""
        async with async_session_maker() as session:
            return await user_list_manager.get_user_list_by_id(list_id, session)

    async def get_list_member_slack_ids(self, list_id: int) -> List[str]:
        """Get all member slack IDs of a user list."""
        async with async_session_maker() as session:
            return await user_list_manager.get_list_member_slack_ids(list_id, session)

    async def update_list_members(
        self, list_id: int, slack_ids: List[str], user_names: List[str]
    ) -> None:
        """Replace all members of a list with new slack IDs."""
        async with async_session_maker() as session:
            await user_list_manager.update_list_members(
                list_id, slack_ids, user_names, session
            )

    async def remove_list_members(self, list_id: int, slack_ids: List[str]) -> None:
        """Remove specific users from a list by their slack IDs."""
        async with async_session_maker() as session:
            await user_list_manager.remove_members(list_id, slack_ids, session)

    async def delete_user_list(self, list_id: int) -> bool:
        """Delete a user list and all its members."""
        async with async_session_maker() as session:
            return await user_list_manager.delete_user_list(list_id, session)

    async def ensure_default_lists(self) -> None:
        """
        Verify that default user lists exist, creating them if necessary,
        and ensuring they are up-to-date with current active users.
        """
        from shared.services.database.users.crud import user_manager

        async with async_session_maker() as session:
            all_list = await user_list_manager.get_user_list_by_name("all", session)

            if not all_list:
                print("INFO: Creating default 'all' user list...")
                all_list = await self.create_user_list(
                    name="all", description="All active users"
                )
            else:
                print(
                    "INFO: Default 'all' user list already exists. Refreshing members..."
                )

            active_users = await user_manager.get_active_users(session)

            if active_users:
                slack_ids = [u.slack_id for u in active_users]
                user_names = [u.realname for u in active_users]
                await self.update_list_members(all_list.id, slack_ids, user_names)
                print(f"INFO: Updated 'all' user list with {len(slack_ids)} users.")
            else:
                # If no active users, ensure the list is empty
                await self.update_list_members(all_list.id, [], [])
                print("INFO: 'all' user list cleared (no active users found).")
