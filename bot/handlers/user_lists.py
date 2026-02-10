import asyncio
import json

from handlers.base import BaseHandler
from services.slack_block_handler.users_lists_control import (
    UserListUpdateModal,
    UsersListsControlBlock,
)
from services.users_lists_handler.main import UsersListsHandler as Ulm


class UserListHandler(BaseHandler):
    """
    Handler for user list management commands and actions.
    """

    def __init__(self, bot):
        super().__init__(bot)
        self._selected_user_lists = {}

    def register(self):
        """Register user list handlers."""
        self.app.command("/users_lists_management")(
            self.bot.admin_check(self.show_user_lists_manager)
        )
        self.app.action("user_list_select")(self.handle_user_list_selection)
        self.app.action("user_list_update")(self.handle_user_list_update_click)
        self.app.action("user_list_create")(self.handle_user_list_create)
        self.app.view("user_list_update_modal")(self.handle_user_list_update_submit)

    def show_user_lists_manager(self, ack, body, say):
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
            asyncio.run(Ulm().create_user_list(name=new_list_name))

            user_lists = asyncio.run(Ulm().get_all_surveys())

            control_block = UsersListsControlBlock(user_lists=user_lists)

            self.app.client.chat_update(
                channel=channel_id,
                ts=thread_ts,
                text="User lists:",
                blocks=control_block.build(),
            )

            say(
                f"User list `{new_list_name}` created and UI refreshed!",
                thread_ts=thread_ts,
            )

        except Exception as e:
            print(f"[ERROR] Failed to create user list: {e}")
            say(f"Error creating user list: {e}", thread_ts=thread_ts)

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

            current_member_ids = []
            if user_list.members:
                for member in user_list.members:
                    if member.slack_id:
                        current_member_ids.append(member.slack_id)

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

        metadata = json.loads(view["private_metadata"])
        list_id = metadata["list_id"]
        target_channel = metadata.get("channel")
        target_thread = metadata.get("ts")

        user_id = body["user"]["id"]

        values = view.get("state", {}).get("values", {})
        selected_users = []
        for block_id, block_values in values.items():
            for action_id, action_value in block_values.items():
                if action_id == "update_members_select":
                    selected_users = action_value.get("selected_users", [])
                    break

        try:
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

            if target_channel and target_thread:
                self.app.client.chat_postMessage(
                    channel=target_channel,
                    thread_ts=target_thread,
                    text=f"User list updated! {len(selected_users)} members set.",
                )
            else:
                self.app.client.chat_postMessage(
                    channel=user_id,
                    text=f"User list updated! {len(selected_users)} members set.",
                )
        except Exception as e:
            print(f"[ERROR] Failed to update list members: {e}")
            if target_channel and target_thread:
                self.app.client.chat_postMessage(
                    channel=target_channel,
                    thread_ts=target_thread,
                    text=f"Error updating list: {e}",
                )
            else:
                self.app.client.chat_postMessage(
                    channel=user_id,
                    text=f"Error updating list: {e}",
                )
