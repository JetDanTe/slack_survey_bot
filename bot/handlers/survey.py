import asyncio
import io
import typing as tp

import pandas as pd
from handlers.base import BaseHandler
from services.reminder_service import ReminderService
from services.slack_block_handler import (
    SurveyControlBlock,
    SurveyCreationModal,
    SurveyResponseBlock,
)
from services.survey_handler.main import SurveyHandler as Sh
from services.user_handler.main import UserHandler

from shared.schemas.surveys import SurveyResponseCreate, SurveySentMessageCreate
from shared.services.database.core.dependencies import async_session_maker
from shared.services.database.surveys.crud import (
    survey_manager,
    survey_response_manager,
    survey_sent_message_manager,
)
from shared.services.database.user_lists.crud import user_list_manager


class SurveyHandler(BaseHandler):
    """
    Handler for survey management commands and actions.
    """

    def register(self):
        """Register survey handlers."""
        self.app.command("/survey_manager")(
            self.bot.admin_check(self.show_survey_manager)
        )
        self.app.command("/survey_create")(self.handle_survey_create_command)
        self.app.view("survey_create_modal")(self.handle_survey_create_submission)

        self.app.action("survey_start")(self.handle_survey_start)
        self.app.action("survey_stop")(self.handle_survey_stop)
        self.app.action("survey_unanswered")(self.handle_survey_unanswered)
        self.app.action("survey_set_lists")(self.handle_set_users_lists)
        self.app.action("survey_submit_answer")(self.handle_survey_submit)
        self.app.action("survey_empty_2")(self.handle_survey_empty)
        self.app.action("survey_user_list_include")(self.handle_list_selection_change)
        self.app.action("survey_user_list_exclude")(self.handle_list_selection_change)
        self.app.action("survey_remind_now")(self.handle_remind_now)

    def show_survey_manager(self, ack, body, say):
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
                    if "Survey Control Panel" in blocks_str:
                        try:
                            self.app.client.chat_delete(
                                channel=channel_id, ts=msg["ts"]
                            )
                        except Exception as e:
                            self.logger.error(
                                "failed_to_delete_message", error=str(e), ts=msg["ts"]
                            )

        except Exception as e:
            self.logger.error(
                "failed_to_cleanup_old_messages", error=str(e), channel_id=channel_id
            )

        surveys = asyncio.run(Sh().get_active_surveys())
        for s in surveys:
            user_lists = asyncio.run(self._get_user_lists_for_block(s.id))

            incl_ids = s.users_incl.split(",") if s.users_incl else []
            excl_ids = s.users_excl.split(",") if s.users_excl else []

            control_block = SurveyControlBlock(
                survey_id=s.id,
                survey_name=s.survey_name,
                survey_text=s.survey_text,
                available_user_lists=user_lists,
                current_users_incl=incl_ids,
                current_users_excl=excl_ids,
                reminder_interval_hours=s.reminder_interval_hours or 0,
                reminders_sent_count=s.reminders_sent_count or 0,
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
        ack()
        self.logger.info(
            "survey_started", user_id=owner_id, survey_name=audit_message[0]
        )

        survey = asyncio.run(
            Sh().create_survey(
                survey_name=audit_message[0],
                survey_text=audit_message[1],
                owner_slack_id=owner_id,
                owner_name=owner_name,
            )
        )

        user_lists = asyncio.run(self._get_user_lists_for_block(survey.id))

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

    async def _get_user_lists_for_modal(self) -> tp.List[tp.Dict[str, str]]:
        """Helper to fetch user lists for modal options."""
        async with async_session_maker() as session:
            lists = await user_list_manager.get_all_user_lists(session)
            return [
                {"text": {"type": "plain_text", "text": ul.name}, "value": str(ul.id)}
                for ul in lists
            ]

    def handle_survey_create_command(self, ack, body, client):
        """Handle /survey_create command to open modal."""
        ack()
        user_lists = asyncio.run(self._get_user_lists_for_modal())
        channel_id = body.get("channel_id")

        modal = SurveyCreationModal(channel_id=channel_id, user_lists=user_lists)

        client.views_open(
            trigger_id=body["trigger_id"],
            view=modal.build(),
        )

    def handle_survey_create_submission(self, ack, body, view, client):
        """Handle survey creation modal submission."""
        ack()
        user_id = body["user"]["id"]
        channel_id = view.get("private_metadata")
        values = view["state"]["values"]

        survey_name = values["survey_name_block"]["survey_name_input"]["value"]
        survey_text = values["survey_text_block"]["survey_text_input"]["value"]

        self.logger.info("survey_created", user_id=user_id, survey_name=survey_name)

        incl_ids = []
        if (
            "survey_include_block" in values
            and values["survey_include_block"]["survey_include_select"][
                "selected_options"
            ]
        ):
            incl_ids = [
                opt["value"]
                for opt in values["survey_include_block"]["survey_include_select"][
                    "selected_options"
                ]
            ]

        excl_ids = []
        if (
            "survey_exclude_block" in values
            and values["survey_exclude_block"]["survey_exclude_select"][
                "selected_options"
            ]
        ):
            excl_ids = [
                opt["value"]
                for opt in values["survey_exclude_block"]["survey_exclude_select"][
                    "selected_options"
                ]
            ]

        users_incl = ",".join(incl_ids) if incl_ids else None
        users_excl = ",".join(excl_ids) if excl_ids else None

        reminder_interval_hours = 0
        if "survey_reminder_block" in values and values["survey_reminder_block"][
            "survey_reminder_input"
        ].get("value"):
            try:
                reminder_interval_hours = float(
                    values["survey_reminder_block"]["survey_reminder_input"]["value"]
                )
            except (ValueError, TypeError):
                reminder_interval_hours = 0

        survey = asyncio.run(
            Sh().create_survey(
                survey_name=survey_name,
                survey_text=survey_text,
                owner_slack_id=user_id,
                owner_name=body["user"]["name"],
                reminder_interval_hours=reminder_interval_hours,
            )
        )

        if users_incl or users_excl:
            asyncio.run(
                self._update_survey_moderation_lists(survey.id, users_incl, users_excl)
            )
            survey.users_incl = users_incl
            survey.users_excl = users_excl

        all_lists = asyncio.run(self._get_user_lists_for_block(survey.id))

        control_block = SurveyControlBlock(
            survey_id=survey.id,
            survey_name=survey.survey_name,
            survey_text=survey.survey_text,
            available_user_lists=all_lists,
            current_users_incl=incl_ids,
            current_users_excl=excl_ids,
            reminder_interval_hours=reminder_interval_hours,
        )

        target_channel = channel_id if channel_id else user_id

        client.chat_postMessage(
            channel=target_channel,
            text=f"Survey '{survey.survey_name}' created!",
            blocks=control_block.build(),
        )

    def handle_survey_start(self, ack, body, say):
        """Handle the Start button click."""
        ack()
        survey_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")

        self.logger.info("survey_start_clicked", user_id=user_id, survey_id=survey_id)
        say(
            f"<@{user_id}> clicked Start for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )

        async def start_survey_process():
            async with async_session_maker() as session:
                survey = await survey_manager.get_survey_by_id(int(survey_id), session)
                if not survey:
                    say(f"Survey {survey_id} not found.", thread_ts=thread_ts)
                    return

                incl_ids = survey.users_incl.split(",") if survey.users_incl else []
                excl_ids = survey.users_excl.split(",") if survey.users_excl else []

                target_users = set()

                for list_id in incl_ids:
                    members = await user_list_manager.get_list_member_slack_ids(
                        int(list_id), session
                    )
                    target_users.update(members)

                for list_id in excl_ids:
                    members = await user_list_manager.get_list_member_slack_ids(
                        int(list_id), session
                    )
                    target_users.difference_update(members)

                self.logger.debug(
                    "target_users_after_exclusion", target_users=target_users
                )
                if self.bot.debug:
                    self.logger.debug("bot_admins", admins=self.bot.admins)

                response_block = SurveyResponseBlock(
                    survey_id=survey.id,
                    survey_name=survey.survey_name,
                    question_text=survey.survey_text,
                )
                blocks = response_block.build_with_submit()

                sent_count = 0
                for target_user in target_users:
                    if self.bot.debug:
                        if target_user not in self.bot.admins:
                            self.logger.debug(
                                "skipping_survey_for_non_admin", target_user=target_user
                            )
                            continue

                    try:
                        result = self.app.client.chat_postMessage(
                            channel=target_user,
                            blocks=blocks,
                            text=f"Survey: {survey.survey_name}",
                        )
                        self.logger.info(
                            "message_sent_to_user",
                            target_user=target_user,
                            survey_id=survey.id,
                        )
                        sent_count += 1

                        await survey_sent_message_manager.add_sent_message(
                            sent_data=SurveySentMessageCreate(
                                survey_id=survey.id,
                                receiver_slack_id=target_user,
                                message_ts=result["ts"],
                            ),
                            session=session,
                        )
                    except Exception as e:
                        self.logger.error(
                            "error_sending_to_user",
                            error=str(e),
                            target_user=target_user,
                        )

                say(
                    f"Survey '{survey.survey_name}' started! Sent to {sent_count} users.",
                    thread_ts=thread_ts,
                )

        asyncio.run(start_survey_process())

    def handle_survey_stop(self, ack, body, say):
        """Handle the Stop button click."""
        ack()
        survey_id = body["actions"][0]["value"]
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        channel_id = body["container"].get("channel_id")

        self.logger.info("survey_stop_clicked", user_id=user_id, survey_id=survey_id)

        async def stop_survey():
            try:
                survey = await Sh().close_survey(int(survey_id))
                if survey:
                    async with async_session_maker() as session:
                        responses = (
                            await survey_response_manager.get_responses_by_survey(
                                int(survey_id), session
                            )
                        )

                    if responses:
                        data = []
                        for response in responses:
                            data.append(
                                {
                                    "User Real Name": response.responder_name,
                                    "Response": response.answer,
                                }
                            )

                        df = pd.DataFrame(data)

                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine="openpyxl") as writer:
                            df.to_excel(writer, index=False, sheet_name="Responses")
                        output.seek(0)

                        try:
                            self.app.client.files_upload_v2(
                                channel=channel_id,
                                thread_ts=thread_ts,
                                title=f"Survey Results - {survey.survey_name}",
                                filename=f"survey_results_{survey_id}.xlsx",
                                file=output,
                                initial_comment=f"Here are the results for survey '{survey.survey_name}'",
                            )
                        except Exception as e:
                            self.logger.error(
                                "failed_to_upload_survey_results", error=str(e)
                            )
                            say(
                                f"Failed to upload survey results: {e}",
                                thread_ts=thread_ts,
                            )

                    say(
                        f"Survey '{survey.survey_name}' stopped by <@{user_id}>",
                        thread_ts=thread_ts,
                    )
                    try:
                        self.app.client.chat_delete(channel=channel_id, ts=thread_ts)
                    except Exception as e:
                        self.logger.error(
                            "failed_to_delete_survey_control_panel", error=str(e)
                        )

                    async with async_session_maker() as session:
                        sent_messages = (
                            await survey_sent_message_manager.get_sent_messages(
                                survey_id=int(survey_id), session=session
                            )
                        )
                        for msg in sent_messages:
                            try:
                                self.app.client.chat_delete(
                                    channel=msg.receiver_slack_id, ts=msg.message_ts
                                )
                            except Exception as e:
                                self.logger.error(
                                    "failed_to_delete_message",
                                    error=str(e),
                                    receiver_slack_id=msg.receiver_slack_id,
                                )

                else:
                    say(
                        f"Survey with ID {survey_id} not found.",
                        thread_ts=thread_ts,
                    )
            except Exception as e:
                say(
                    f"Error stopping survey: {e}",
                    thread_ts=thread_ts,
                )

        asyncio.run(stop_survey())

    def handle_survey_unanswered(self, ack, body, say):
        """Handle the Unanswered button click."""
        ack()
        survey_id = int(body["actions"][0]["value"])
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        self.logger.info(
            "survey_unanswered_requested", user_id=user_id, survey_id=survey_id
        )

        say(
            f"<@{user_id}> requested unanswered list for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )

        async def get_unanswered_users():
            async with async_session_maker() as session:
                sent_messages = await survey_sent_message_manager.get_sent_messages(
                    survey_id=survey_id, session=session
                )
                sent_user_ids = {msg.receiver_slack_id for msg in sent_messages}
                responses = await survey_response_manager.get_responses_by_survey(
                    survey_id=survey_id, session=session
                )
                responded_user_ids = {r.responder_slack_id for r in responses}

                unanswered_user_ids = sent_user_ids - responded_user_ids

                if not unanswered_user_ids:
                    say(
                        "All users have responded to this survey!",
                        thread_ts=thread_ts,
                    )
                    return

                mentions = []
                user_handler = UserHandler()
                for s_id in unanswered_user_ids:
                    user = await user_handler.get_user_by_slack_id(s_id)
                    if user:
                        mentions.append(f"@{user.username}")
                    else:
                        mentions.append(f"<@{s_id}>")

                if mentions:
                    say(
                        f"Unanswered users: {' '.join(mentions)}",
                        thread_ts=thread_ts,
                    )
                else:
                    say(
                        "No unanswered users found in records.",
                        thread_ts=thread_ts,
                    )

        asyncio.run(get_unanswered_users())

    def handle_set_users_lists(self, ack, body, say):
        """Handle the Set Users lists button click."""
        ack()
        user_id = body["user"]["id"]
        survey_id = int(body["actions"][0]["value"])
        thread_ts = body["container"].get("message_ts")
        self.logger.info("survey_set_users_lists", user_id=user_id, survey_id=survey_id)

        state_values = body.get("state", {}).get("values", {})

        incl_list_ids = []
        excl_list_ids = []
        incl_list_names = []
        excl_list_names = []

        incl_block_id = "survey_user_list_include_block"
        excl_block_id = "survey_user_list_exclude_block"

        incl_action_id = "survey_user_list_include"
        excl_action_id = "survey_user_list_exclude"

        for block_id, actions in state_values.items():
            if block_id == incl_block_id:
                options = actions.get(incl_action_id, {}).get("selected_options", [])
                for opt in options:
                    incl_list_ids.append(opt["value"].split(":")[1])
                    incl_list_names.append(opt["text"]["text"])
            elif block_id == excl_block_id:
                options = actions.get(excl_action_id, {}).get("selected_options", [])
                for opt in options:
                    excl_list_ids.append(opt["value"].split(":")[1])
                    excl_list_names.append(opt["text"]["text"])

        users_incl = ",".join(incl_list_ids) if incl_list_ids else None
        users_excl = ",".join(excl_list_ids) if excl_list_ids else None

        try:
            asyncio.run(
                self._update_survey_moderation_lists(survey_id, users_incl, users_excl)
            )
            say(
                f"<@{user_id}> moderation lists updated for survey `{survey_id}`.\n"
                f"Include: *{', '.join(incl_list_names) if incl_list_names else 'None'}*\n"
                f"Exclude: *{', '.join(excl_list_names) if excl_list_names else 'None'}*",
                thread_ts=thread_ts,
            )
        except Exception as e:
            say(
                f"<@{user_id}> Error updating moderation lists: {e}",
                thread_ts=thread_ts,
            )

    def handle_list_selection_change(self, ack, body, say):
        """Handle immediate user list selection changes."""
        ack()

        survey_id = None
        blocks = body.get("message", {}).get("blocks", [])
        for block in blocks:
            if block.get("type") == "actions":
                elements = block.get("elements", [])
                for element in elements:
                    if element.get("action_id") == "survey_start":
                        try:
                            survey_id = int(element.get("value"))
                            break
                        except (ValueError, TypeError):
                            pass
                if survey_id is not None:
                    break

        if survey_id is None:
            self.logger.error("could_not_determine_survey_id")
            return

        state_values = body.get("state", {}).get("values", {})

        def get_selected_ids(mode):
            block_id = f"survey_user_list_{mode}_block"
            action_key = f"survey_user_list_{mode}"

            options = (
                state_values.get(block_id, {})
                .get(action_key, {})
                .get("selected_options", [])
            )
            return [opt["value"].split(":")[1] for opt in options]

        incl_ids = get_selected_ids("include")
        excl_ids = get_selected_ids("exclude")

        users_incl = ",".join(incl_ids) if incl_ids else None
        users_excl = ",".join(excl_ids) if excl_ids else None

        asyncio.run(
            self._update_survey_moderation_lists(survey_id, users_incl, users_excl)
        )

    async def _update_survey_moderation_lists(
        self, survey_id: int, users_incl: tp.Optional[str], users_excl: tp.Optional[str]
    ):
        async with async_session_maker() as session:
            await survey_manager.update_survey_moderation_lists(
                survey_id, users_incl, users_excl, session
            )

    def handle_remind_now(self, ack, body, say):
        """Handle the Remind Now button click - send immediate reminder."""
        ack()
        survey_id = int(body["actions"][0]["value"])
        user_id = body["user"]["id"]
        thread_ts = body["container"].get("message_ts")
        self.logger.info("survey_remind_now", user_id=user_id, survey_id=survey_id)

        say(
            f"<@{user_id}> triggered an immediate reminder for survey ID: `{survey_id}`",
            thread_ts=thread_ts,
        )

        reminder_service = ReminderService(self.app)
        asyncio.run(reminder_service.send_immediate_reminder(survey_id))

        say(
            f"Reminder sent for survey `{survey_id}`! :bell:",
            thread_ts=thread_ts,
        )

    def handle_survey_empty(self, ack, body, say):
        """Handle empty button clicks (placeholder for future functionality)."""
        ack()
        survey_id = body["actions"][0]["value"]
        action_id = body["actions"][0]["action_id"]
        thread_ts = body["container"].get("message_ts")
        self.logger.info(
            "survey_empty_clicked", survey_id=survey_id, action_id=action_id
        )
        say(
            f"Empty button `{action_id}` clicked for survey ID: `{survey_id}` (not implemented)",
            thread_ts=thread_ts,
        )

    def update_users(self, ack, body, say):
        """Gather user data from Slack. Update slack user status if_delete and add new users."""
        ack()

        self.bot.common_handler.safe_say(
            receiver=body.get("event").get("user"),
            message="Starting user update...",
            say_func=say,
        )
        try:
            users = self.app.client.users_list()["members"]
            result = asyncio.run(UserHandler().update_users(users))

            self.logger.info(
                "users_updated",
                created=result["created"],
                updated=result["updated"],
                errors=result["errors"],
            )
            self.bot.common_handler.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Users updated successfully.\nCreated: {result['created']}\nUpdated: {result['updated']}\nErrors: {result['errors']}",
                say_func=say,
            )
        except Exception as e:
            self.logger.error("failed_to_update_users", error=str(e))
            self.bot.common_handler.safe_say(
                receiver=body.get("event").get("user"),
                message=f"Failed to update users: {e}",
                say_func=say,
            )

    def handle_survey_submit(self, ack, body, say):
        """Handle survey answer submission."""
        ack()
        survey_id = int(body["actions"][0]["value"])
        user_id = body["user"]["id"]
        user_name = body["user"]["name"]

        values = body.get("state", {}).get("values", {})
        block_id = f"survey_response_{survey_id}"
        answer = values.get(block_id, {}).get("survey_answer_input", {}).get("value")

        if not answer:
            self.bot.common_handler.safe_say(
                receiver=user_id,
                message="Error: Could not retrieve answer.",
                say_func=say,
            )
            return

        async def save_response():
            try:
                async with async_session_maker() as session:
                    if await survey_response_manager.check_user_responded(
                        survey_id, user_id, session
                    ):
                        self.logger.info(
                            "user_already_responded",
                            user_id=user_id,
                            survey_id=survey_id,
                        )
                        thread_ts = body["container"]["message_ts"]
                        say(
                            text=f"You have already responded to this survey, <@{user_id}>",
                            thread_ts=thread_ts,
                        )
                        return

                    survey_response_data = SurveyResponseCreate(
                        survey_id=survey_id,
                        responder_slack_id=user_id,
                        responder_name=user_name,
                        answer=str(answer),
                    )
                    await survey_response_manager.add_response(
                        response_data=survey_response_data, session=session
                    )

                    survey = await survey_manager.get_survey_by_id(survey_id, session)
                    if survey:
                        response_block = SurveyResponseBlock(
                            survey_id=survey.id,
                            survey_name=survey.survey_name,
                            question_text=survey.survey_text,
                            is_submitted=True,
                        )
                        try:
                            channel_id = body.get("container", {}).get("channel_id")
                            ts = body.get("container", {}).get("message_ts")

                            if channel_id and ts:
                                self.app.client.chat_update(
                                    channel=channel_id,
                                    ts=ts,
                                    blocks=response_block.build_with_submit(),
                                    text=f"Survey: {survey.survey_name} (Answered)",
                                )
                                self.logger.debug(
                                    "successfully_updated_message",
                                    ts=ts,
                                    channel_id=channel_id,
                                )
                            else:
                                self.logger.warning(
                                    "could_not_find_channel_id_or_ts",
                                    body_container=body.get("container"),
                                )

                        except Exception as update_err:
                            self.logger.error(
                                "failed_to_update_message_with_checkmark",
                                error=str(update_err),
                            )

                thread_ts = body["container"]["message_ts"]
                say(text=f"Thanks for answer, <@{user_id}>", thread_ts=thread_ts)
                self.logger.info(
                    "user_answered_survey", user_id=user_id, survey_id=survey_id
                )

            except Exception as e:
                self.logger.error("error_saving_response", error=str(e))

                if self.bot.debug:
                    receiver_name = user_name
                    self.logger.debug(
                        "would_say_error_saving_response",
                        error=str(e),
                        receiver_name=receiver_name,
                    )
                else:
                    say(
                        f"Error saving response: {e}",
                        thread_ts=body["container"]["message_ts"],
                    )

        asyncio.run(save_response())
