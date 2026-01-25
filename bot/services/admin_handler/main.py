from shared.schemas.users import Admin
from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.users.crud import UserCRUD_Manager
from shared.services.settings.main import Settings


class AdminHandler:
    def __init__(self, settings: Settings):
        self.first_admin_id = settings.SLACK_ADMIN_ID

    async def setup_first_admin(self):
        async with async_session_maker() as session:
            admin_manager = UserCRUD_Manager(model=Admin)
            self.first_admin = await admin_manager.create_user(
                Admin(slack_id=self.first_admin_id, is_admin=True), session
            )

    async def get_all_admins(self):
        async with async_session_maker() as session:
            admin_manager = UserCRUD_Manager(model=Admin)
            admins = await admin_manager.get_all(session=session)
            return admins
