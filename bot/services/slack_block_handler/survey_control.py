"""Survey control panel block builder."""

from typing import Dict, List

from pydantic import BaseModel, Field


class SurveyControlBlock(BaseModel):
    """
    Builds Slack blocks for survey control panel with action buttons.

    Each button contains the survey_id in its payload value.
    """

    survey_id: int = Field(..., description="Survey ID from database")
    survey_name: str = Field(..., min_length=1, max_length=255)
    survey_text: str = Field(default="", description="Survey message text to display")
    available_user_lists: List[Dict[str, str]] = Field(
        default_factory=list, description="List of user lists with 'text' and 'value'"
    )
    current_users_incl: List[str] = Field(
        default_factory=list, description="IDs of currently included user lists"
    )
    current_users_excl: List[str] = Field(
        default_factory=list, description="IDs of currently excluded user lists"
    )

    def build(self) -> list:
        """Build complete Slack blocks for survey control panel."""
        return [
            self._build_header(),
            self._build_divider(),
            self._build_input("include"),
            self._build_input("exclude"),
            self._build_actions(),
        ]

    def _build_header(self) -> dict:
        """Build header section with survey info."""
        text = (
            f"*Survey Control Panel*\n"
            f"Survey: *{self.survey_name}*\n"
            f"ID: `{self.survey_id}`"
        )
        if self.survey_text:
            text += f"\n\n`{self.survey_text}`"
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text,
            },
        }

    def _build_divider(self) -> dict:
        """Build divider block."""
        return {"type": "divider"}

    def _build_actions(self) -> dict:
        """Build actions block with control elements."""
        return {
            "type": "actions",
            "elements": [
                self._button("Start", "survey_start", style="primary"),
                self._button("Stop", "survey_stop", style="danger"),
                self._button("Unanswered", "survey_unanswered"),
                self._button("Set Users lists", "survey_set_lists"),
            ],
        }

    def _build_input(self, mode: str) -> dict:
        """
        Build input block for user list selection.

        :param mode: 'include' or 'exclude'
        """
        label_text = "Users list include" if mode == "include" else "User lists exclude"
        block_id = f"survey_user_list_{mode}_block"
        action_id = f"survey_user_list_{mode}"
        current_ids = (
            self.current_users_incl if mode == "include" else self.current_users_excl
        )

        return {
            "type": "input",
            "block_id": block_id,
            "element": self._user_list_dropdown(action_id, current_ids),
            "label": {
                "type": "plain_text",
                "text": label_text,
                "emoji": True,
            },
            "optional": True,
        }

    def _button(self, text: str, action_id: str, style: str | None = None) -> dict:
        """Build a single button element with survey_id as payload."""
        button = {
            "type": "button",
            "text": {"type": "plain_text", "text": text, "emoji": True},
            "action_id": action_id,
            "value": str(self.survey_id),
        }
        if style:
            button["style"] = style
        return button

    def _user_list_dropdown(self, action_id: str, selected_ids: List[str]) -> dict:
        """Build multi-select dropdown menu for user lists selection."""

        options = []
        if self.available_user_lists:
            for ul in self.available_user_lists:
                options.append(
                    {
                        "text": {"type": "plain_text", "text": ul["text"]},
                        "value": ul["value"],
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

        select_block = {
            "type": "multi_static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select User Lists",
                "emoji": True,
            },
            "action_id": action_id,
            "options": options,
        }

        if selected_ids and self.available_user_lists:
            initial_options = []
            for opt in options:
                # Value format in available_user_lists is "{survey_id}:{list_id}"
                # We need to extract the list_id to compare with selected_ids
                list_id = opt["value"].split(":")[1]
                if list_id in selected_ids:
                    initial_options.append(opt)

            if initial_options:
                select_block["initial_options"] = initial_options

        return select_block
