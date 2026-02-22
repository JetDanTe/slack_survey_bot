import asyncio
import typing as tp

from handlers.common import CommonHandler
from handlers.survey import SurveyHandler
from handlers.user_lists import UserListHandler
from services.admin.main import AdminHandler
from services.reminder_service import ReminderService
from services.user_handler.main import UserHandler
from services.users_lists_handler.main import UsersListsHandler
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from shared.services.settings.main import settings
from shared.utils.logger import get_logger, setup_logger


class SurveyBot:
    def __init__(self):
        setup_logger()
        self.logger = get_logger("SurveyBot")
        self.debug = settings.DEBUG
        self.app = App(token=settings.SLACK_BOT_TOKEN)

        # Initialize admins
        self.admins = asyncio.run(self.initialize_admins(settings))

        # Initialize Handler Modules
        self.common_handler = CommonHandler(self)
        self.survey_handler = SurveyHandler(self)
        self.user_list_handler = UserListHandler(self)

        # Initialize Handlers
        self.common_handler.register()
        self.survey_handler.register()
        self.user_list_handler.register()

        # Initialize User Lists
        asyncio.run(self.initialize_user_lists())

        # Socket mode handler to connect the bot to Slack
        self.handler = SocketModeHandler(self.app, settings.SLACK_APP_TOKEN)

        # Sync users on startup
        asyncio.run(self.sync_slack_users())

        # Initialize Reminder Service
        self.reminder_service = ReminderService(self.app)

    async def initialize_admins(self, settings) -> tp.List[str]:
        """
        Setup the first admin and fetch all admins.
        """
        handler = AdminHandler(settings)
        await handler.setup_first_admin()
        return await handler.get_all_admins()

    async def initialize_user_lists(self):
        """
        Setup default user lists if they don't exist.
        """
        handler = UsersListsHandler()
        await handler.ensure_default_lists()

    async def sync_slack_users(self):
        """
        Fetch all users from Slack and update the local database.
        """
        self.logger.info("syncing_slack_users_on_startup")
        try:
            users_response = self.app.client.users_list()
            if users_response["ok"]:
                result = await UserHandler().update_users(users_response["members"])
                self.logger.info(
                    "users_synced",
                    created=result["created"],
                    updated=result["updated"],
                    errors=result["errors"],
                )
            else:
                self.logger.error(
                    "slack_users_list_failed", error=users_response.get("error")
                )
        except Exception as e:
            self.logger.error("failed_to_sync_users", error=str(e))

    def admin_check(self, func):
        """Decorator to check if the command is issued by an admin."""

        def wrapper(ack, body, say, *args, **kwargs):
            ack()
            user_id = (
                body.get("user_id")
                or body.get("user", {}).get("id")
                or body.get("event", {}).get("user")
            )

            if user_id not in self.admins:
                self.common_handler.safe_say(
                    receiver=user_id,
                    message="You are not authorized to perform this action.",
                    say_func=say,
                )
                return
            return func(ack, body, say, *args, **kwargs)

        return wrapper

    def start(self):
        """Connects to Slack in socket mode"""
        self.logger.info(
            f"Starting bot in {'DEBUG' if self.debug else 'PRODUCTION'} mode..."
        )
        self.reminder_service.start()
        self.handler.start()
