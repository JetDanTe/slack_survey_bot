import asyncio
import typing as tp

from handlers.base import BaseHandler
from services.slack_block_handler import SurveyControlBlock, SurveyCreationModal
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
        self.app.command("/survey_create")(self.handle_survey_create_command)
        self.app.view("survey_create_modal")(self.handle_survey_create_submission)

        self.app.action("survey_start")(self.handle_survey_start)
        self.app.action("survey_stop")(self.handle_survey_stop)
        self.app.action("survey_unanswered")(self.handle_survey_unanswered)
        self.app.action("survey_set_lists")(self.handle_set_users_lists)
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

            incl_ids = s.users_incl.split(",") if s.users_incl else []
            excl_ids = s.users_excl.split(",") if s.users_excl else []

            control_block = SurveyControlBlock(
                survey_id=s.id,
                survey_name=s.survey_name,
                survey_text=s.survey_text,
                available_user_lists=user_lists,
                current_users_incl=incl_ids,
                current_users_excl=excl_ids,
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

    async def _get_user_lists_for_modal(self) -> tp.List[tp.Dict[str, str]]:
        """Helper to fetch user lists for modal options."""
        async with async_session_maker() as session:
            lists = await user_list_manager.get_all_user_lists(session)
            return [
                {"text": {"type": "plain_text", "text": ul.name}, "value": str(ul.id)}
                for ul in lists
            ]

    def handle_survey_create_command(self, ack, body, client):
        """Handle /survey_create command to open modal."""
        ack()
        user_lists = asyncio.run(self._get_user_lists_for_modal())
        channel_id = body.get("channel_id")

        modal = SurveyCreationModal(channel_id=channel_id, user_lists=user_lists)

        client.views_open(
            trigger_id=body["trigger_id"],
            view=modal.build(),
        )

    def handle_survey_create_submission(self, ack, body, view, client):
        """Handle survey creation modal submission."""
        ack()
        user_id = body["user"]["id"]
        channel_id = view.get("private_metadata")
        values = view["state"]["values"]

        survey_name = values["survey_name_block"]["survey_name_input"]["value"]
        survey_text = values["survey_text_block"]["survey_text_input"]["value"]

        incl_ids = []
        if (
            "survey_include_block" in values
            and values["survey_include_block"]["survey_include_select"][
                "selected_options"
            ]
        ):
            incl_ids = [
                opt["value"]
                for opt in values["survey_include_block"]["survey_include_select"][
                    "selected_options"
                ]
            ]

        excl_ids = []
        if (
            "survey_exclude_block" in values
            and values["survey_exclude_block"]["survey_exclude_select"][
                "selected_options"
            ]
        ):
            excl_ids = [
                opt["value"]
                for opt in values["survey_exclude_block"]["survey_exclude_select"][
                    "selected_options"
                ]
            ]

        users_incl = ",".join(incl_ids) if incl_ids else None
        users_excl = ",".join(excl_ids) if excl_ids else None

        survey = asyncio.run(
            Sh().create_survey(
                survey_name=survey_name,
                survey_text=survey_text,
                owner_slack_id=user_id,
                owner_name=body["user"]["name"],
            )
        )

        if users_incl or users_excl:
            asyncio.run(
                self._update_survey_moderation_lists(survey.id, users_incl, users_excl)
            )
            survey.users_incl = users_incl
            survey.users_excl = users_excl

        all_lists = asyncio.run(self._get_user_lists_for_block(survey.id))

        control_block = SurveyControlBlock(
            survey_id=survey.id,
            survey_name=survey.survey_name,
            survey_text=survey.survey_text,
            available_user_lists=all_lists,
            current_users_incl=incl_ids,
            current_users_excl=excl_ids,
        )

        target_channel = channel_id if channel_id else user_id

        client.chat_postMessage(
            channel=target_channel,
            text=f"Survey '{survey.survey_name}' created!",
            blocks=control_block.build(),
        )

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

    def handle_set_users_lists(self, ack, body, say):
        """Handle the Set Users lists button click."""
        ack()
        user_id = body["user"]["id"]
        survey_id = int(body["actions"][0]["value"])
        thread_ts = body["container"].get("message_ts")

        # Extract selected options from state
        state_values = body.get("state", {}).get("values", {})

        incl_list_ids = []
        excl_list_ids = []
        incl_list_names = []
        excl_list_names = []

        for block_id, actions in state_values.items():
            if block_id == "survey_user_list_include_block":
                options = actions.get("survey_user_list_include", {}).get(
                    "selected_options", []
                )
                for opt in options:
                    incl_list_ids.append(opt["value"].split(":")[1])
                    incl_list_names.append(opt["text"]["text"])
            elif block_id == "survey_user_list_exclude_block":
                options = actions.get("survey_user_list_exclude", {}).get(
                    "selected_options", []
                )
                for opt in options:
                    excl_list_ids.append(opt["value"].split(":")[1])
                    excl_list_names.append(opt["text"]["text"])

        users_incl = ",".join(incl_list_ids) if incl_list_ids else None
        users_excl = ",".join(excl_list_ids) if excl_list_ids else None

        try:
            asyncio.run(
                self._update_survey_moderation_lists(survey_id, users_incl, users_excl)
            )
            say(
                f"<@{user_id}> moderation lists updated for survey `{survey_id}`.\n"
                f"Include: *{', '.join(incl_list_names) if incl_list_names else 'None'}*\n"
                f"Exclude: *{', '.join(excl_list_names) if excl_list_names else 'None'}*",
                thread_ts=thread_ts,
            )
        except Exception as e:
            say(
                f"<@{user_id}> Error updating moderation lists: {e}",
                thread_ts=thread_ts,
            )

    async def _update_survey_moderation_lists(
        self, survey_id: int, users_incl: tp.Optional[str], users_excl: tp.Optional[str]
    ):
        async with async_session_maker() as session:
            await survey_manager.update_survey_moderation_lists(
                survey_id, users_incl, users_excl, session
            )

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
