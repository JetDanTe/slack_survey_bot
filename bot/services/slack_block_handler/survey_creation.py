"""Survey creation modal builder."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SurveyCreationModal(BaseModel):
    """
    Builds Slack modal for survey creation.
    """

    channel_id: Optional[str] = Field(
        None, description="Channel ID where command was triggered"
    )
    user_lists: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of user lists for dropdowns"
    )

    def build(self) -> dict:
        """Build complete modal view payload."""
        blocks = [
            {
                "type": "input",
                "block_id": "survey_name_block",
                "label": {"type": "plain_text", "text": "Survey Name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "survey_name_input",
                },
            },
            {
                "type": "input",
                "block_id": "survey_text_block",
                "label": {"type": "plain_text", "text": "Survey Text"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "survey_text_input",
                    "multiline": True,
                },
            },
        ]

        if self.user_lists:
            blocks.append(
                {
                    "type": "input",
                    "block_id": "survey_include_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "Include Lists"},
                    "element": {
                        "type": "multi_static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select lists to include",
                        },
                        "options": self.user_lists,
                        "action_id": "survey_include_select",
                    },
                }
            )
            blocks.append(
                {
                    "type": "input",
                    "block_id": "survey_exclude_block",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "Exclude Lists"},
                    "element": {
                        "type": "multi_static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select lists to exclude",
                        },
                        "options": self.user_lists,
                        "action_id": "survey_exclude_select",
                    },
                }
            )

        return {
            "type": "modal",
            "callback_id": "survey_create_modal",
            "private_metadata": self.channel_id,
            "title": {"type": "plain_text", "text": "Create Survey"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": blocks,
        }
