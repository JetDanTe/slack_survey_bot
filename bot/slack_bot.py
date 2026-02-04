import asyncio
import typing as tp

from services.admin_handler.main import AdminHandler
from services.slack_block_handler import SurveyControlBlock
from services.survey_handler.main import SurveyHandler
from services.user_handler.main import UserHandler
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


class AuditBot:
    def __init__(self, settings):
        self.debug = settings.DEBUG
        self.app = App(token=settings.SLACK_BOT_TOKEN)
        # Initialize admins
        self.admins = asyncio.run(self.initialize_admins(settings))

        # Define bot commands and event handlers
        # Audit control
        self.app.command("/survey_manager")(self.admin_check(self.show_survey_manager))

        # User commands
        self.app.message()(self.shadow_answer)
        self.app.event("message")(self.handle_message_events)

        # Survey button action handlers
        self.app.action("survey_start")(self.handle_survey_start)
        self.app.action("survey_stop")(self.handle_survey_stop)
        self.app.action("survey_unanswered")(self.handle_survey_unanswered)
        self.app.action("survey_user_list")(self.handle_user_list_select)
        self.app.action("survey_empty_2")(self.handle_survey_empty)

        # Socket mode handler to connect the bot to Slack
        self.handler = SocketModeHandler(self.app, settings.SLACK_APP_TOKEN)

    async def initialize_admins(self, settings) -> tp.List[str]:
        """
        Setup the first admin and fetch all admins.
        """
        handler = AdminHandler(settings)
        await handler.setup_first_admin()
        return await handler.get_all_admins()

    def admin_check(self, func):
        """Decorator to check if the command is issued by an admin."""

        def wrapper(ack, body, say, *args, **kwargs):
            ack()
            user_id = body["user_id"]
            if user_id not in self.admins:
                self.safe_say(
                    receiver=body.get("event").get("user"),
                    message="You are not authorized to perform this action.",
                    say_func=say,
                )
                return
            return func(ack, body, say, *args, **kwargs)

        return wrapper

    def not_implemented(self, ack, body, say):
        """Plug for handling uncreated commands"""
        ack()
        self.safe_say(
            receiver=body.get("event").get("user"),
            message="Command not implemented, yet.",
            say_func=say,
        )

    def show_survey_manager(self, ack, body, say):
        ack()

        channel_id = body.get("channel_id")

        try:
            # Get bot's user ID
            auth_test = self.app.client.auth_test()
            bot_user_id = auth_test["user_id"]

            # Fetch recent history
            history = self.app.client.conversations_history(
                channel=channel_id, limit=20
            )
            messages = history.get("messages", [])

            for msg in messages:
                # Check if message is from this bot and contains "Survey Control Panel"
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

        surveys = asyncio.run(SurveyHandler().get_all_surveys())
        for s in surveys:
            control_block = SurveyControlBlock(
                survey_id=s.id,
                survey_name=s.survey_name,
                survey_text=s.survey_text,
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
        ack()  # Acknowledge the command

        survey = asyncio.run(
            SurveyHandler().create_survey(
                survey_name=audit_message[0],
                survey_text=audit_message[1],
                owner_slack_id=owner_id,
                owner_name=owner_name,
            )
        )

        # Build the survey control message with 5 buttons
        control_block = SurveyControlBlock(
            survey_id=survey.id,
            survey_name=survey.survey_name,
            survey_text=audit_message[1],
        )

        say(
            text=f"Survey '{survey.survey_name}' started!",
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

    def handle_user_list_select(self, ack, body, say):
        """Handle the User List dropdown selection."""
        ack()
        selected_option = body["actions"][0]["selected_option"]
        value = selected_option["value"]
        text = selected_option["text"]["text"]
        user_id = body["user"]["id"]

        # Parse value which is "survey_id:list_type"
        if ":" in value:
            survey_id, list_type = value.split(":", 1)
        else:
            survey_id = value
            list_type = "unknown"

        say(
            f"<@{user_id}> selected user list: *{text}* (`{list_type}`) for survey ID: `{survey_id}`"
        )
        # TODO: Implement actual user list application logic

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

    # def send_message(self, user_id, message):
    #     """Alarm. Danger. This func can send messages to real people in your workspace."""
    #     if not self.debug:
    #         try:
    #             response = self.app.client.conversations_open(users=user_id)
    #             dm_channel_id = response["channel"]["id"]

    #             self.app.client.chat_postMessage(channel=dm_channel_id, text=message)
    #         except SlackApiError as e:
    #             print(f"Error sending message: {e.response['error']}")
    #     else:
    #         print(
    #             f'Message sending initialized. Message not sent - Debug "{self.debug}"'
    #         )

    def collect_answer(self, ack, body, say):
        """Takes the user's answer and puts it into the database"""
        ack()
        survey_answer = asyncio.run(
            SurveyHandler().add_survey_response(
                survey_id=1, respondent_slack_id=body["user_id"], responses=body["text"]
            )
        )
        print(survey_answer)
        # if not self.audit_session:
        #     say(
        #         "There is no active audit session. Please wait until an audit is started."
        #     )
        # else:
        #     # existed_answer = self.database_manager.check_if_answer_exist(data)
        #     # if not existed_answer:
        #     self.audit_session.add_response(data)
        #     say(
        #         f"Thank you <@{body['user_id']}>! Your response '{body['text']}' has been recorded."
        #     )
        # else:
        #    say("You already answered.")

    def close_audit(self, ack, body, say):
        """Close audit and return audit report .xlsx file"""
        ack()  # Acknowledge the command
        channel_id = body.get("channel_id")
        if self.audit_session is not None:
            self.audit_session.close_session()
            audit_summary = self.audit_session.get_audit_summary()
            self.app.client.files_upload_v2(
                channel=channel_id,
                initial_comment="Audit closed!\nHere's report file :smile:",
                file=audit_summary,
            )
            self.audit_session = None
        else:
            say("There is no active audit session to close.")

    def update_users(self, ack, body, say):
        """Gather user data from Slack. Update slack user status if_delete and add new users."""
        ack()

        self.safe_say(
            receiver=body.get("event").get("user"),
            message="Starting user update...",
            say_func=say,
        )
        try:
            users = self.app.client.users_list()["members"]
            result = asyncio.run(UserHandler().update_users(users))

            self.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Users updated successfully.\nCreated: {result['created']}\nUpdated: {result['updated']}\nErrors: {result['errors']}",
                say_func=say,
            )
        except Exception as e:
            self.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Failed to update users: {e}",
                say_func=say,
            )

    def _format_user_list(self, users: tp.Text) -> tp.List[tp.Dict]:
        """
        Format list of users from string to dict
        :param users: Str
        :return: List of dicts
        """
        users = users.split(" ")
        formatted_users = [
            {"id": None, "name": user.replace("@", ""), "profile": {"real_name": None}}
            for user in users
        ]
        return formatted_users

    def _handle_list_of_users(self, body: tp.Dict, update_type: str) -> tp.Text:
        """
        Handle list of users for different update types (admin or ignore).

        :param users: List of usernames to update
        :param update_type: Type of update ('admin' or 'ignore')
        :return: List of not found users
        :raises ValueError: If invalid update_type provided
        """
        if update_type not in ["admin", "ignore"]:
            raise ValueError("update_type must be either 'admin' or 'ignore'")

        text = f"{update_type.title()} list updated"
        users = self._format_user_list(body.get("text"))
        not_found_users = self.database_manager.update_users(
            users,
            to_ignore=(update_type == "ignore"),
            to_admin=(update_type == "admin"),
            by_name=True,
        )
        if not_found_users:
            text += f"\nCould not find the following users: {', '.join(user.get('name') for user in not_found_users)}"
        return text

    def update_ignore(self, ack, body, say):
        """Update list of users which audit can ignore"""
        ack()
        result = self._handle_list_of_users(body, "ignore")

        self.safe_say(
            receiver=body.get("event").get("user"), message=f"{result}", say_func=say
        )

    def update_admin(self, ack, body, say):
        """Set column is_admin to True in the database"""
        ack()
        result = self._handle_list_of_users(body, "admin")
        self.safe_say(
            receiver=body.get("event").get("user"), message=f"{result}", say_func=say
        )

    def show_users(self, ack, body, say):
        """Universal command to show a list of users. Depends on which command is triggered."""
        ack()
        command_mapping = {
            "/ignore_show": "Ignored users:",
            "/admin_show": "Admin users:",
            "/audit_unanswered": "Audit unanswered:",
        }
        command_name = body.get("command")
        self.safe_say(
            receiver=body.get("user_id"),
            message=f"{self.admins}",
            say_func=say,
        )
        if not self.audit_session and command_name == "/audit_unanswered":
            self.safe_say(
                receiver=body.get("event").get("user"),
                message="There is no active audit session",
                say_func=say,
            )
        else:
            users_to_show = self.database_manager.get_users(
                command_name,
                None if not self.audit_session else self.audit_session.table_name,
            )
            if isinstance(users_to_show, str):
                self.safe_say(
                    receiver=body.get("event").get("user"),
                    message=f"{users_to_show}",
                    say_func=say,
                )
            else:
                users_to_show = "\n".join(f"<@{user.id}>" for user in users_to_show)
                text = f"{command_mapping.get(command_name, 'Users:')}\n{users_to_show}"
                self.safe_say(
                    receiver=body.get("event").get("user"),
                    message=f"{text}",
                    say_func=say,
                )

    def show_user_help(self, ack, body, say):
        """Return to user string with help information"""
        ack()
        self.safe_say(
            receiver=body.get("event").get("user"),
            message="Use next command to answer:\n /answer <your_location>\n"
            "For example:\n /answer Paris",
            say_func=say,
        )

    def shadow_answer(self, ack, body, say):
        """Trigger on any not slash command messages"""
        ack()
        self.safe_say(
            receiver=body.get("event").get("user"),
            message="Sorry, do not understand. Use /help command or ask manager.",
            say_func=say,
            channel=body.get("event").get("channel"),
            thread_ts=body.get("event").get("ts"),
        )

    def safe_say(self, receiver: str, message: str, say_func, **kwargs):
        """Wrapper for say() that respects debug mode."""
        receiver = asyncio.run(UserHandler().get_user_realname(receiver))
        if self.debug:
            print(f'[DEBUG] Would say: "{message}" to {receiver}')
        else:
            say_func(message, **kwargs)

    def handle_message_events(self, body, logger):
        """Acknowledge message events (like message_changed) to avoid unhandled warnings."""
        logger.debug(f"Received message event: {body}")
        pass

    def start(self):
        """Connects to Slack in socket mode"""
        self.handler.start()
