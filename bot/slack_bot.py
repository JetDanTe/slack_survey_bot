import asyncio
import json
import typing as tp

from services.admin.main import AdminHandler
from services.slack_block_handler import SurveyControlBlock
from services.slack_block_handler.users_lists_control import (
    UserListUpdateModal,
    UsersListsControlBlock,
)
from services.survey_handler.main import SurveyHandler
from services.user_handler.main import UserHandler
from services.users_lists_handler.main import UsersListsHandler as Ulm
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.surveys.crud import survey_manager
from shared.services.database.user_lists.crud import user_list_manager
from shared.services.settings.main import settings


class SurveyBot:
    def __init__(self):
        self.debug = settings.DEBUG
        self.app = App(token=settings.SLACK_BOT_TOKEN)
        # Initialize admins
        self.admins = asyncio.run(self.initialize_admins(settings))

        # Define bot commands and event handlers
        # Audit control
        self.app.command("/survey_manager")(self.admin_check(self.show_survey_manager))
        self.app.command("/users_lists_management")(
            self.admin_check(self.show_user_lists_manager)
        )

        # User commands
        self.app.message()(self.shadow_answer)
        self.app.event("message")(self.handle_message_events)

        # Survey button action handlers
        self.app.action("survey_start")(self.handle_survey_start)
        self.app.action("survey_stop")(self.handle_survey_stop)
        self.app.action("survey_unanswered")(self.handle_survey_unanswered)
        self.app.action("survey_user_list")(self.handle_user_list_select)
        self.app.action("survey_empty_2")(self.handle_survey_empty)

        # User list management action handlers
        self.app.action("user_list_select")(self.handle_user_list_selection)
        self.app.action("user_list_update")(self.handle_user_list_update_click)
        self.app.action("user_list_create")(self.handle_user_list_create)

        # Modal submission handlers
        self.app.view("user_list_update_modal")(self.handle_user_list_update_submit)

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
        ack()  # Acknowledge the command

        survey = asyncio.run(
            SurveyHandler().create_survey(
                survey_name=audit_message[0],
                survey_text=audit_message[1],
                owner_slack_id=owner_id,
                owner_name=owner_name,
            )
        )

        # Fetch available user lists
        user_lists = asyncio.run(self._get_user_lists_for_block(survey.id))

        # Build the survey control message with 5 buttons
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

        # Update DB
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

    def show_user_lists_manager(self, ack, body, say):
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
                    if "User Lists Control Panel" in blocks_str:
                        try:
                            self.app.client.chat_delete(
                                channel=channel_id, ts=msg["ts"]
                            )
                        except Exception as e:
                            print(f"[ERROR] Failed to delete message {msg['ts']}: {e}")

        except Exception as e:
            print(f"[ERROR] Error cleaning up old messages: {e}")

        user_lists = asyncio.run(Ulm().get_all_surveys())
        control_block = UsersListsControlBlock(user_lists=user_lists)

        say(
            text="User lists:",
            blocks=control_block.build(),
        )

    def handle_user_list_create(self, ack, body, say):
        """Handle the Create List button click."""
        ack()

        # Get the new list name from the state
        state_values = body.get("state", {}).get("values", {})
        new_list_name = None
        for block_id, block_values in state_values.items():
            for action_id, action_value in block_values.items():
                if action_id == "new_list_name_input":
                    new_list_name = action_value.get("value")
                    break

        channel_id = body.get("channel", {}).get("id") or body.get("container", {}).get(
            "channel_id"
        )
        thread_ts = body.get("container", {}).get("message_ts")

        if not new_list_name:
            say("Please enter a name for the new list.", thread_ts=thread_ts)
            return

        try:
            # Create the list
            asyncio.run(Ulm().create_user_list(name=new_list_name))

            # Refresh all user lists
            user_lists = asyncio.run(Ulm().get_all_surveys())

            # Rebuild control block
            control_block = UsersListsControlBlock(user_lists=user_lists)

            # Update the original message to show the new list in dropdown
            self.app.client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text="User lists:",
                blocks=control_block.build(),
            )

            # Confirmation in thread
            say(
                f"✅ User list `{new_list_name}` created and UI refreshed!",
                thread_ts=thread_ts,
            )

        except Exception as e:
            print(f"[ERROR] Failed to create user list: {e}")
            say(f"❌ Error creating user list: {e}", thread_ts=thread_ts)

    # Store selected user list per channel for button actions
    _selected_user_lists = {}

    def handle_user_list_selection(self, ack, body, say):
        """Handle the dropdown selection to store the selected user list."""
        ack()
        selected = body["actions"][0].get("selected_option")
        if selected:
            list_id = selected["value"]
            channel_id = body.get("channel", {}).get("id") or body.get(
                "container", {}
            ).get("channel_id")
            if channel_id:
                self._selected_user_lists[channel_id] = list_id

    def handle_user_list_update_click(self, ack, body, say):
        """Handle the Update button click - opens modal."""
        ack()
        channel_id = body.get("channel", {}).get("id") or body.get("container", {}).get(
            "channel_id"
        )
        trigger_id = body["trigger_id"]

        # Get the selected list from the dropdown in the same message
        state_values = body.get("state", {}).get("values", {})
        selected_list_id = None
        for block_id, block_values in state_values.items():
            for action_id, action_value in block_values.items():
                if action_id == "user_list_select":
                    selected_option = action_value.get("selected_option")
                    if selected_option:
                        selected_list_id = selected_option["value"]
                    break

        if not selected_list_id or selected_list_id == "none":
            thread_ts = body.get("container", {}).get("message_ts")
            say("Please select a user list first.", thread_ts=thread_ts)
            return

        try:
            list_id = int(selected_list_id)
            user_list = asyncio.run(Ulm().get_user_list_with_members(list_id))

            if not user_list:
                thread_ts = body.get("container", {}).get("message_ts")
                say("User list not found.", thread_ts=thread_ts)
                return

            # Get current member slack IDs - directly from the member table
            current_member_ids = []
            if user_list.members:
                for member in user_list.members:
                    if member.slack_id:
                        current_member_ids.append(member.slack_id)

            # Extract thread context
            thread_ts = body.get("container", {}).get("message_ts")

            modal = UserListUpdateModal(
                list_id=list_id,
                list_name=user_list.name,
                channel_id=channel_id,
                thread_ts=thread_ts,
                current_member_ids=current_member_ids,
            )

            self.app.client.views_open(
                trigger_id=trigger_id,
                view=modal.build(),
            )
        except Exception as e:
            print(f"[ERROR] Failed to open update modal: {e}")
            thread_ts = body.get("container", {}).get("message_ts")
            say(f"Error opening update modal: {e}", thread_ts=thread_ts)

    def handle_user_list_update_submit(self, ack, body, view, say):
        """Handle the Update modal submission."""
        ack()

        # Parse metadata
        metadata = json.loads(view["private_metadata"])
        list_id = metadata["list_id"]
        target_channel = metadata.get("channel")
        target_thread = metadata.get("ts")

        user_id = body["user"]["id"]

        # Get selected users from the modal
        values = view.get("state", {}).get("values", {})
        selected_users = []
        for block_id, block_values in values.items():
            for action_id, action_value in block_values.items():
                if action_id == "update_members_select":
                    selected_users = action_value.get("selected_users", [])
                    break

        try:
            # Get user names for the slack_ids from Slack API
            user_names = []
            for slack_id in selected_users:
                try:
                    user_info = self.app.client.users_info(user=slack_id)
                    user_name = user_info["user"].get("real_name") or user_info[
                        "user"
                    ].get("name", slack_id)
                    user_names.append(user_name)
                except Exception:
                    user_names.append(slack_id)  # Fallback to slack_id

            asyncio.run(Ulm().update_list_members(list_id, selected_users, user_names))

            # Send confirmation directly to the thread if available, otherwise DM user
            if target_channel and target_thread:
                self.app.client.chat_postMessage(
                    channel=target_channel,
                    thread_ts=target_thread,
                    text=f"✅ User list updated! {len(selected_users)} members set.",
                )
            else:
                self.app.client.chat_postMessage(
                    channel=user_id,
                    text=f"✅ User list updated! {len(selected_users)} members set.",
                )
        except Exception as e:
            print(f"[ERROR] Failed to update list members: {e}")
            if target_channel and target_thread:
                self.app.client.chat_postMessage(
                    channel=target_channel,
                    thread_ts=target_thread,
                    text=f"❌ Error updating list: {e}",
                )
            else:
                self.app.client.chat_postMessage(
                    channel=user_id,
                    text=f"❌ Error updating list: {e}",
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
