import asyncio
import typing as tp

from handlers.base import BaseHandler
from services.slack_block_handler import SurveyControlBlock
from services.survey_handler.main import SurveyHandler as Sh
from services.user_handler.main import UserHandler

from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.surveys.crud import survey_manager
from shared.services.database.user_lists.crud import user_list_manager


class SurveyHandler(BaseHandler):
    """
    Handler for survey management commands and actions.
    """

    def register(self):
        """Register survey handlers."""
        self.app.command("/survey_manager")(
            self.bot.admin_check(self.show_survey_manager)
        )
        self.app.action("survey_start")(self.handle_survey_start)
        self.app.action("survey_stop")(self.handle_survey_stop)
        self.app.action("survey_unanswered")(self.handle_survey_unanswered)
        self.app.action("survey_user_list")(self.handle_user_list_select)
        self.app.action("survey_empty_2")(self.handle_survey_empty)

    def show_survey_manager(self, ack, body, say):
        ack()
        channel_id = body.get("channel_id")

        try:
            auth_test = self.app.client.auth_test()
            bot_user_id = auth_test["user_id"]

            history = self.app.client.conversations_history(
                channel=channel_id, limit=20
            )
            messages = history.get("messages", [])

            for msg in messages:
                if msg.get("user") == bot_user_id:
                    blocks_str = str(msg.get("blocks", []))
                    if "Survey Control Panel" in blocks_str:
                        try:
                            self.app.client.chat_delete(
                                channel=channel_id, ts=msg["ts"]
                            )
                        except Exception as e:
                            print(f"[ERROR] Failed to delete message {msg['ts']}: {e}")

        except Exception as e:
            print(f"[ERROR] Error cleaning up old messages: {e}")

        surveys = asyncio.run(Sh().get_all_surveys())
        for s in surveys:
            user_lists = asyncio.run(self._get_user_lists_for_block(s.id))

            control_block = SurveyControlBlock(
                survey_id=s.id,
                survey_name=s.survey_name,
                survey_text=s.survey_text,
                available_user_lists=user_lists,
            )

            say(
                text=f"Survey '{s.survey_name}':",
                blocks=control_block.build(),
            )

    def start_survey(self, ack, body, say):
        """Audit process main function"""
        audit_message = body.get("text").splitlines()
        owner_id = body.get("user_id")
        owner_name = body.get("user_name")
        ack()

        survey = asyncio.run(
            Sh().create_survey(
                survey_name=audit_message[0],
                survey_text=audit_message[1],
                owner_slack_id=owner_id,
                owner_name=owner_name,
            )
        )

        user_lists = asyncio.run(self._get_user_lists_for_block(survey.id))

        control_block = SurveyControlBlock(
            survey_id=survey.id,
            survey_name=survey.survey_name,
            survey_text=audit_message[1],
            available_user_lists=user_lists,
        )

        say(
            text=f"Survey '{survey.survey_name}' started!",
            blocks=control_block.build(),
        )

    async def _get_user_lists_for_block(
        self, survey_id: int
    ) -> tp.List[tp.Dict[str, str]]:
        """Helper to fetch and format user lists for UI."""
        async with async_session_maker() as session:
            lists = await user_list_manager.get_all_user_lists(session)
            return [{"text": ul.name, "value": f"{survey_id}:{ul.id}"} for ul in lists]

    def handle_survey_start(self, ack, body, say):
        """Handle the Start button click."""
        ack()
        survey_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        say(
            f"<@{user_id}> clicked Start for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )
        # TODO: Implement actual survey start logic

    def handle_survey_stop(self, ack, body, say):
        """Handle the Stop button click."""
        ack()
        survey_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        say(
            f"<@{user_id}> clicked Stop for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )
        # TODO: Implement actual survey stop logic

    def handle_survey_unanswered(self, ack, body, say):
        """Handle the Unanswered button click."""
        ack()
        survey_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        say(
            f"<@{user_id}> requested unanswered list for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )
        # TODO: Implement actual unanswered users logic

    def handle_user_list_select(self, ack, body, say):
        """Handle the User List dropdown selection."""
        ack()
        user_id = body["user"]["id"]

        selected_options = body["actions"][0].get("selected_options")

        if not selected_options:
            return

        first_val = selected_options[0]["value"]
        thread_ts = body["container"].get("message_ts")
        if ":" not in first_val:
            say(
                f"<@{user_id}> Error: Invalid option format.",
                thread_ts=thread_ts,
            )
            return

        survey_id_str, _ = first_val.rsplit(":", 1)
        try:
            survey_id = int(survey_id_str)
        except ValueError:
            say(
                f"<@{user_id}> Error: Invalid survey ID.",
                thread_ts=thread_ts,
            )
            return

        list_ids = []
        list_names = []
        for opt in selected_options:
            val = opt["value"]
            parts = val.rsplit(":", 1)
            if len(parts) == 2:
                list_ids.append(int(parts[1]))
                list_names.append(opt["text"]["text"])

        try:
            asyncio.run(self._update_survey_lists(survey_id, list_ids))
            say(
                f"<@{user_id}> updated lists for survey `{survey_id}`: *{', '.join(list_names)}*",
                thread_ts=thread_ts,
            )
        except Exception as e:
            say(
                f"<@{user_id}> Error updating lists: {e}",
                thread_ts=thread_ts,
            )

    async def _update_survey_lists(self, survey_id: int, list_ids: tp.List[int]):
        async with async_session_maker() as session:
            await survey_manager.update_survey_user_lists(survey_id, list_ids, session)

    def handle_survey_empty(self, ack, body, say):
        """Handle empty button clicks (placeholder for future functionality)."""
        ack()
        survey_id = body["actions"][0]["value"]
        action_id = body["actions"][0]["action_id"]
        thread_ts = body["container"].get("message_ts")
        say(
            f"Empty button `{action_id}` clicked for survey ID: `{survey_id}` (not implemented)",
            thread_ts=thread_ts,
        )

    def update_users(self, ack, body, say):
        """Gather user data from Slack. Update slack user status if_delete and add new users."""
        ack()

        self.bot.common_handler.safe_say(
            receiver=body.get("event").get("user"),
            message="Starting user update...",
            say_func=say,
        )
        try:
            users = self.app.client.users_list()["members"]
            result = asyncio.run(UserHandler().update_users(users))

            self.bot.common_handler.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Users updated successfully.\nCreated: {result['created']}\nUpdated: {result['updated']}\nErrors: {result['errors']}",
                say_func=say,
            )
        except Exception as e:
            self.bot.common_handler.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Failed to update users: {e}",
                say_func=say,
            )
