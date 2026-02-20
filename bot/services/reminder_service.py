"""
Reminder Service - Background loop for sending gentle survey reminders.

Periodically checks active surveys and sends reminder messages
to users who haven't responded yet.
"""

import asyncio
import threading

from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.surveys.crud import (
    survey_manager,
    survey_response_manager,
    survey_sent_message_manager,
)


class ReminderService:
    """
    Background service that periodically sends reminders
    for active surveys to users who haven't responded.
    """

    CHECK_INTERVAL_SECONDS = 60 * 15  # Check every 1 minute

    def __init__(self, app):
        """
        :param app: The Slack Bolt App instance (for sending messages).
        """
        self.app = app
        self._stop_event = threading.Event()

    def start(self):
        """Start the reminder loop in a background thread."""
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()
        print("[REMINDER] Reminder service started.")

    def stop(self):
        """Signal the reminder loop to stop."""
        self._stop_event.set()
        print("[REMINDER] Reminder service stop requested.")

    def _run_loop(self):
        """Main loop that runs in a background thread."""
        while not self._stop_event.is_set():
            try:
                asyncio.run(self.check_and_send_reminders())
            except Exception as e:
                print(f"[REMINDER][ERROR] Error in reminder loop: {e}")

            # Wait, but check for stop signal periodically
            self._stop_event.wait(timeout=self.CHECK_INTERVAL_SECONDS)

    async def check_and_send_reminders(self):
        """
        Check all active surveys for pending reminders and send them.
        """
        async with async_session_maker() as session:
            due_surveys = await survey_manager.get_surveys_needing_reminder(session)

        if not due_surveys:
            return

        print(f"[REMINDER] Found {len(due_surveys)} survey(s) needing reminders.")

        for survey in due_surveys:
            try:
                await self._send_reminders_for_survey(survey)
            except Exception as e:
                print(f"[REMINDER][ERROR] Failed to process survey {survey.id}: {e}")

    async def _send_reminders_for_survey(self, survey):
        """
        Send reminder messages for a single survey to unanswered users.
        Reminders are sent as thread replies to the original survey message.
        """
        async with async_session_maker() as session:
            sent_messages = await survey_sent_message_manager.get_sent_messages(
                survey_id=survey.id, session=session
            )
            user_message_map = {
                msg.receiver_slack_id: msg.message_ts for msg in sent_messages
            }

            if not user_message_map:
                print(
                    f"[REMINDER] Survey {survey.id} ('{survey.survey_name}'): "
                    f"No sent messages found. Survey may not have been started yet. Skipping."
                )
                return

            responses = await survey_response_manager.get_responses_by_survey(
                survey_id=survey.id, session=session
            )
            responded_user_ids = {r.responder_slack_id for r in responses}

            unanswered_user_ids = set(user_message_map.keys()) - responded_user_ids

            if not unanswered_user_ids:
                print(
                    f"[REMINDER] Survey {survey.id} ('{survey.survey_name}'): "
                    f"All {len(user_message_map)} users have responded. Skipping."
                )
                return

            reminder_count = (survey.reminders_sent_count or 0) + 1
            reminder_text = (
                f":bell: *Gentle Reminder*\n\n"
                f"Hi! This is a friendly reminder to complete the survey "
                f"*{survey.survey_name}*.\n\n"
                f"Please take a moment to provide your response. "
                f"Thank you! :pray:"
            )

            sent_count = 0
            for user_id in unanswered_user_ids:
                original_msg_ts = user_message_map.get(user_id)
                if not original_msg_ts:
                    continue
                try:
                    self.app.client.chat_postMessage(
                        channel=user_id,
                        thread_ts=original_msg_ts,
                        text=reminder_text,
                        blocks=[
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": reminder_text,
                                },
                            }
                        ],
                    )
                    sent_count += 1
                except Exception as e:
                    print(
                        f"[REMINDER][ERROR] Failed to send reminder to {user_id}: {e}"
                    )

            print(
                f"[REMINDER] Survey {survey.id} ('{survey.survey_name}'): "
                f"Sent reminder #{reminder_count} to {sent_count}/{len(unanswered_user_ids)} users."
            )

            # Update reminder tracking
            await survey_manager.update_reminder_status(survey.id, session)

    async def send_immediate_reminder(self, survey_id: int):
        """
        Send an immediate reminder for a specific survey (triggered manually).
        """
        async with async_session_maker() as session:
            survey = await survey_manager.get_survey_by_id(survey_id, session)
            if not survey or not survey.is_active:
                print(f"[REMINDER] Survey {survey_id} not found or not active.")
                return 0

        return await self._send_reminders_for_survey(survey)
