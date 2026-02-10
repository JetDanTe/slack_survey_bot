import json
from typing import List, Optional

from pydantic import BaseModel, Field

from shared.schemas.user_lists import UserList


class UsersListsControlBlock(BaseModel):
    """
    Builds Slack blocks for user lists control panel.

    Shows a dropdown to select a user list and Update/Delete buttons.
    """

    user_lists: List[UserList] = Field(
        default_factory=list, description="List of user lists from database"
    )

    class Config:
        arbitrary_types_allowed = True

    def build(self) -> list:
        """Build complete Slack blocks for user lists control panel."""
        return [
            self._build_header(),
            self._build_divider(),
            self._build_name_input(),
            self._build_create_list_section(),
            self._build_divider(),
            self._build_input(),
            self._build_actions(),
        ]

    def _build_header(self) -> dict:
        """Build header section with panel title."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*User Lists Control Panel*\nSelect a user list to manage its members.",
            },
        }

    def _build_divider(self) -> dict:
        """Build divider block."""
        return {"type": "divider"}

    def _build_name_input(self) -> dict:
        """Build plain-text input for new list name."""
        return {
            "type": "input",
            "block_id": "new_list_name_block",
            "element": {
                "type": "plain_text_input",
                "action_id": "new_list_name_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Enter list name...",
                },
            },
            "label": {
                "type": "plain_text",
                "text": "New List Name",
            },
        }

    def _build_input(self) -> dict:
        """Build input block for user list selection."""
        return {
            "type": "input",
            "block_id": "user_list_select_block",
            "element": self._user_list_dropdown(),
            "label": {
                "type": "plain_text",
                "text": "Select User List",
                "emoji": True,
            },
            "optional": False,
        }

    def _build_create_list_section(self) -> dict:
        """Build section for creating a new user list."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Create New User List*\nEnter a name and click create.",
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "Create", "emoji": True},
                "action_id": "user_list_create",
                "style": "primary",
            },
            "block_id": "user_list_create_section",
        }

    def _build_actions(self) -> dict:
        """Build actions block with Update button."""
        return {
            "type": "actions",
            "block_id": "user_list_actions_block",
            "elements": [
                self._button("Update Members", "user_list_update", style="primary"),
            ],
        }

    def _button(self, text: str, action_id: str, style: str | None = None) -> dict:
        """Build a button element."""
        button = {
            "type": "button",
            "text": {"type": "plain_text", "text": text, "emoji": True},
            "action_id": action_id,
        }
        if style:
            button["style"] = style
        return button

    def _user_list_dropdown(self) -> dict:
        """Build static select dropdown for user list selection."""
        options = []
        if self.user_lists:
            for ul in self.user_lists:
                options.append(
                    {
                        "text": {"type": "plain_text", "text": ul.name},
                        "value": str(ul.id),
                    }
                )
        else:
            # Fallback if no lists
            options = [
                {
                    "text": {"type": "plain_text", "text": "No lists available"},
                    "value": "none",
                }
            ]

        return {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Choose a user list",
                "emoji": True,
            },
            "action_id": "user_list_select",
            "options": options,
        }


class UserListUpdateModal(BaseModel):
    """
    Builds Slack modal for updating user list members.
    """

    list_id: int = Field(..., description="User list ID")
    list_name: str = Field(..., description="User list name")
    channel_id: Optional[str] = Field(None, description="Channel ID for threading")
    thread_ts: Optional[str] = Field(None, description="Thread TS for threading")
    current_member_ids: List[str] = Field(
        default_factory=list, description="Current member Slack IDs"
    )

    def build(self) -> dict:
        """Build modal view for updating members."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Updating members for:* `{self.list_name}`",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "update_members_block",
                "element": {
                    "type": "multi_users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select users to be in this list",
                        "emoji": True,
                    },
                    "action_id": "update_members_select",
                    "initial_users": self.current_member_ids
                    if self.current_member_ids
                    else None,
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select Users",
                    "emoji": True,
                },
            },
        ]

        # Remove initial_users if empty (Slack requires at least one if present)
        if not self.current_member_ids:
            del blocks[2]["element"]["initial_users"]

        # Context for threading
        metadata = {
            "list_id": self.list_id,
            "channel": self.channel_id,
            "ts": self.thread_ts,
        }

        return {
            "type": "modal",
            "callback_id": "user_list_update_modal",
            "private_metadata": json.dumps(metadata),
            "title": {
                "type": "plain_text",
                "text": "Update User List",
                "emoji": True,
            },
            "submit": {
                "type": "plain_text",
                "text": "Update",
                "emoji": True,
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
                "emoji": True,
            },
            "blocks": blocks,
        }
