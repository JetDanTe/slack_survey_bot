import typing as tp

from shared.schemas.users import Slack_User
from shared.services.database.core.session import async_session_maker
from shared.services.database.users.crud import user_manager


class UserHandler:
    async def get_user_realname(self, slack_id: str) -> tp.Optional[str]:
        """
        Retrieves the real name of a user by their Slack ID.
        """
        async with async_session_maker() as session:
            user = await user_manager.get(
                session=session, field=Slack_User.slack_id, field_value=slack_id
            )
            if user:
                return user.realname
            return None

    async def get_user_by_slack_id(self, slack_id: str) -> tp.Optional[Slack_User]:
        """
        Retrieves a user object by their Slack ID.
        """
        async with async_session_maker() as session:
            return await user_manager.get(
                session=session, field=Slack_User.slack_id, field_value=slack_id
            )

    async def update_users(self, slack_users: tp.List[tp.Dict]):
        """
        Updates local database with users from Slack.
        """
        created_count = 0
        updated_count = 0
        errors = []

        async with async_session_maker() as session:
            for s_user in slack_users:
                if s_user.get("is_bot") or s_user.get("id") == "USLACKBOT":
                    continue

                user_id = s_user.get("id")
                profile = s_user.get("profile", {})

                user_data = {
                    "slack_id": user_id,
                    "username": s_user.get("name"),
                    "realname": profile.get("real_name") or s_user.get("name"),
                    "is_deleted": s_user.get("deleted", False),
                }

            try:
                existing_user = await user_manager.get(
                    session=session, field=Slack_User.slack_id, field_value=user_id
                )

                if existing_user:
                    update_data = {
                        "username": user_data["username"],
                        "realname": user_data["realname"],
                        "is_deleted": user_data["is_deleted"],
                    }

                    await user_manager.update(session, existing_user, **update_data)
                    updated_count += 1
                else:
                    user_data["is_ignore"] = False
                    new_user = Slack_User(**user_data)
                    await user_manager.create_user(new_user, session)
                    created_count += 1

            except Exception as e:
                print(f"Error processing user {user_id}: {e}")
                errors.append(user_id)

        return {
            "created": created_count,
            "updated": updated_count,
            "errors": len(errors),
        }
