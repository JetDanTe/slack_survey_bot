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
