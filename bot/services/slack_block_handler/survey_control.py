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

    def build(self) -> list:
        """Build complete Slack blocks for survey control panel."""
        return [
            self._build_header(),
            self._build_divider(),
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
            text += f"\n\n{self.survey_text}"
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
                self._user_list_dropdown(),
                self._button("Empty btn", "survey_empty_2"),
            ],
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

    def _user_list_dropdown(self) -> dict:
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

        return {
            "type": "multi_static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select User Lists",
                "emoji": True,
            },
            "action_id": "survey_user_list",
            "options": options,
        }
