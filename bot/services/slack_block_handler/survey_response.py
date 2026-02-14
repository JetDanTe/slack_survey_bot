"""Survey response/user answer block builder."""

from pydantic import BaseModel, Field


class SurveyResponseBlock(BaseModel):
    """
    Builds Slack blocks for user answer input.

    Contains the survey_id in payload for response collection.
    """

    survey_id: int = Field(..., description="Survey ID from database")
    survey_name: str = Field(..., min_length=1, max_length=255)
    question_text: str = Field(
        default="Please provide your answer:", description="Question prompt for user"
    )

    def build(self) -> list:
        """Build complete Slack blocks for user response."""
        return [
            self._build_header(),
            self._build_input(),
        ]

    def _build_header(self) -> dict:
        """Build header section with survey info."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{self.survey_name}*\n{self.question_text}",
            },
        }

    def _build_input(self) -> dict:
        """Build input block for user response."""
        return {
            "type": "input",
            "block_id": f"survey_response_{self.survey_id}",
            "element": {
                "type": "plain_text_input",
                "action_id": "survey_answer_input",
                "multiline": True,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Type your answer here...",
                },
            },
            "label": {"type": "plain_text", "text": "Your Answer", "emoji": True},
        }

    def build_with_submit(self) -> list:
        """Build blocks with a submit button included."""
        blocks = self.build()
        blocks.append(self._build_submit_button())
        return blocks

    def _build_submit_button(self) -> dict:
        """Build submit button for the response."""
        return {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Submit", "emoji": True},
                    "style": "primary",
                    "action_id": "survey_submit_answer",
                    "value": str(self.survey_id),
                }
            ],
        }
