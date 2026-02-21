"""
Reminder Service - Background loop for sending gentle survey reminders.

Periodically checks active surveys and sends reminder messages
to users who haven't responded yet.
"""

import asyncio
import threading

from services.slack_block_handler import SurveyResponseBlock
from services.user_handler.main import UserHandler

from shared.schemas.surveys import SurveySentMessageCreate
from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.surveys.crud import (
    survey_manager,
    survey_response_manager,
    survey_sent_message_manager,
)
from shared.services.database.user_lists.crud import user_list_manager


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
        Also sends the initial survey message to newly added users in the targets.
        """

        async with async_session_maker() as session:
            incl_ids = survey.users_incl.split(",") if survey.users_incl else []
            excl_ids = survey.users_excl.split(",") if survey.users_excl else []

            target_users = set()

            for list_id in incl_ids:
                if list_id.strip():
                    members = await user_list_manager.get_list_member_slack_ids(
                        int(list_id), session
                    )
                    target_users.update(members)

            for list_id in excl_ids:
                if list_id.strip():
                    members = await user_list_manager.get_list_member_slack_ids(
                        int(list_id), session
                    )
                    target_users.difference_update(members)

            sent_messages = await survey_sent_message_manager.get_sent_messages(
                survey_id=survey.id, session=session
            )
            user_message_map = {
                msg.receiver_slack_id: msg.message_ts for msg in sent_messages
            }
            sent_user_ids = set(user_message_map.keys())

            responses = await survey_response_manager.get_responses_by_survey(
                survey_id=survey.id, session=session
            )
            responded_user_ids = {r.responder_slack_id for r in responses}

            new_users = target_users - sent_user_ids

            if new_users:
                print(
                    f"[REMINDER] Survey {survey.id} ('{survey.survey_name}'): "
                    f"Found {len(new_users)} new user(s). Sending initial survey."
                )

                response_block = SurveyResponseBlock(
                    survey_id=survey.id,
                    survey_name=survey.survey_name,
                    question_text=survey.survey_text,
                )
                initial_blocks = response_block.build_with_submit()

                user_handler = UserHandler()

                for target_user in new_users:
                    if (
                        hasattr(self.app, "bot")
                        and hasattr(self.app.bot, "debug")
                        and self.app.bot.debug
                    ):
                        if target_user not in self.app.bot.admins:
                            print(
                                f"[DEBUG] Skipping initial survey for non-admin user {target_user}"
                            )
                            continue

                    user = await user_handler.get_user_by_slack_id(target_user)
                    user_greeting_name = user.username if user else "there"

                    try:
                        result = self.app.client.chat_postMessage(
                            channel=target_user,
                            blocks=initial_blocks,
                            text=f"Hi {user_greeting_name}! Survey: {survey.survey_name}",
                        )
                        await survey_sent_message_manager.add_sent_message(
                            sent_data=SurveySentMessageCreate(
                                survey_id=survey.id,
                                receiver_slack_id=target_user,
                                message_ts=result["ts"],
                            ),
                            session=session,
                        )
                    except Exception as e:
                        print(
                            f"[REMINDER][ERROR] Failed to send initial survey to {target_user}: {e}"
                        )

            unanswered_user_ids = (sent_user_ids - responded_user_ids) & target_users

            if not unanswered_user_ids:
                print(
                    f"[REMINDER] Survey {survey.id} ('{survey.survey_name}'): "
                    f"No pending reminders."
                )
            else:
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
