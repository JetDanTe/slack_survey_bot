from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.users import Admin, Slack_User
from shared.services.database.core.base_crud import BaseCRUDManager


class UserCRUD_Manager(BaseCRUDManager):
    def __init__(self, model=None):
        self.model = model or Slack_User

    async def create_user(
        self, new_user: Admin | Slack_User, session: AsyncSession
    ) -> Admin | Slack_User:
        maybe_user = await self.get(
            session=session, field=self.model.slack_id, field_value=new_user.slack_id
        )
        if maybe_user:
            raise Exception(f"User with id {new_user.slack_id} already exists")

        user_fields = {
            col.name: getattr(new_user, col.name)
            for col in self.model.__table__.columns
        }
        new_user = await self.create(session=session, **user_fields)
        return new_user


user_manager = UserCRUD_Manager()
