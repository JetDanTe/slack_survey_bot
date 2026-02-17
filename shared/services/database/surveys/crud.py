"""
Survey CRUD Manager.

Provides async CRUD operations for Survey and SurveyResponse models.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.schemas.surveys import (
    Survey,
    SurveyCreate,
    SurveyResponse,
    SurveyResponseCreate,
    SurveySentMessage,
    SurveySentMessageCreate,
)
from shared.schemas.user_lists import UserList
from shared.services.database.core.base_crud import BaseCRUDManager


class SurveyCRUDManager(BaseCRUDManager):
    """
    CRUD manager for Survey operations.

    Handles creating surveys, adding responses, and querying survey data.
    """

    def __init__(self, model=None):
        self.model = model or Survey

    async def create_survey(
        self, survey_data: SurveyCreate, session: AsyncSession
    ) -> Survey:
        """
        Create a new survey.

        :param survey_data: Validated Pydantic schema with survey data
        :param session: Async database session
        :return: Created Survey instance
        """
        survey = Survey(
            survey_name=survey_data.survey_name,
            survey_text=survey_data.survey_text,
            owner_slack_id=survey_data.owner_slack_id,
            owner_name=survey_data.owner_name,
            slack_id=survey_data.owner_slack_id,  # Required by Base model
            is_active=True,
            reminder_interval_hours=survey_data.reminder_interval_hours,
        )

        session.add(survey)
        try:
            await session.commit()
            await session.refresh(survey)
            return survey
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error creating survey: {e}")

    async def update_survey_user_lists(
        self, survey_id: int, user_list_ids: List[int], session: AsyncSession
    ) -> Survey:
        """
        Update the user lists associated with a survey.

        :param survey_id: ID of the survey
        :param user_list_ids: List of new UserList IDs
        :param session: AsyncSession
        :return: Updated survey
        """
        survey = await self.get_survey_by_id(
            survey_id, session, include_responses=False
        )
        if not survey:
            raise Exception("Survey not found")

        query = select(UserList).filter(UserList.id.in_(user_list_ids))
        result = await session.execute(query)
        new_lists = result.scalars().all()

        survey.user_lists = list(new_lists)
        session.add(survey)
        await session.commit()
        await session.refresh(survey)
        return survey

    async def update_survey_moderation_lists(
        self,
        survey_id: int,
        users_incl: Optional[str],
        users_excl: Optional[str],
        session: AsyncSession,
    ) -> Survey:
        """
        Update the moderation lists for a survey.

        :param survey_id: ID of the survey
        :param users_incl: Comma-separated user list IDs to include
        :param users_excl: Comma-separated user list IDs to exclude
        :param session: Async database session
        :return: Updated Survey instance
        """
        survey = await self.get_survey_by_id(survey_id, session)
        if not survey:
            raise Exception("Survey not found")

        survey.users_incl = users_incl
        survey.users_excl = users_excl
        session.add(survey)
        try:
            await session.commit()
            await session.refresh(survey)
            return survey
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error updating survey moderation lists: {e}")

    async def get_survey_by_id(
        self, survey_id: int, session: AsyncSession, include_responses: bool = False
    ) -> Optional[Survey]:
        """
        Get a survey by ID.

        :param survey_id: Survey ID to fetch
        :param session: Async database session
        :param include_responses: Whether to eagerly load responses
        :return: Survey instance or None
        """
        query = select(Survey).filter(Survey.id == survey_id)

        if include_responses:
            query = query.options(selectinload(Survey.responses))

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_survey(self, session: AsyncSession) -> Optional[Survey]:
        """
        Get the currently active survey.

        :param session: Async database session
        :return: Active Survey instance or None
        """
        query = select(Survey).filter(Survey.is_active == True)  # noqa: E712
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_surveys(self, session: AsyncSession) -> list[Survey]:
        """
        Get all currently active surveys.

        :param session: Async database session
        :return: List of active Survey instances
        """
        query = select(Survey).filter(Survey.is_active == True)  # noqa: E712
        result = await session.execute(query)
        return list(result.scalars().all())

    async def close_survey(
        self, survey_id: int, session: AsyncSession
    ) -> Optional[Survey]:
        """
        Close a survey by setting is_active to False.

        :param survey_id: Survey ID to close
        :param session: Async database session
        :return: Updated Survey instance or None
        """
        survey = await self.get_survey_by_id(survey_id, session)
        if survey:
            survey.is_active = False
            session.add(survey)
            await session.commit()
            await session.refresh(survey)
        return survey

    async def get_all_surveys(self, session: AsyncSession) -> list[Survey]:
        """
        Get all surveys.

        :param session: Async database session
        :return: List of Survey instances
        """
        query = select(Survey)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_surveys_needing_reminder(self, session: AsyncSession) -> list[Survey]:
        """
        Get active surveys that are due for a reminder.

        Returns surveys where:
        - is_active is True
        - reminder_interval_hours > 0
        - enough time has passed since last_reminder_sent_at (or created_at)
        """
        query = select(Survey).filter(
            Survey.is_active == True,  # noqa: E712
            Survey.reminder_interval_hours > 0,
        )
        result = await session.execute(query)
        surveys = list(result.scalars().all())

        now = datetime.utcnow()
        due_surveys = []
        for survey in surveys:
            reference_time = survey.last_reminder_sent_at or survey.created_at
            interval = timedelta(hours=survey.reminder_interval_hours)
            if now - reference_time >= interval:
                due_surveys.append(survey)
        return due_surveys

    async def update_reminder_status(
        self, survey_id: int, session: AsyncSession
    ) -> Optional[Survey]:
        """
        Update the reminder tracking fields after sending reminders.
        """
        survey = await self.get_survey_by_id(survey_id, session)
        if not survey:
            return None
        survey.last_reminder_sent_at = datetime.utcnow()
        survey.reminders_sent_count = (survey.reminders_sent_count or 0) + 1
        session.add(survey)
        try:
            await session.commit()
            await session.refresh(survey)
            return survey
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error updating reminder status: {e}")


class SurveyResponseCRUDManager(BaseCRUDManager):
    """
    CRUD manager for SurveyResponse operations.

    Handles adding and querying survey responses.
    """

    def __init__(self, model=None):
        self.model = model or SurveyResponse

    async def add_response(
        self, response_data: SurveyResponseCreate, session: AsyncSession
    ) -> SurveyResponse:
        """
        Add a response to a survey.

        :param response_data: Validated Pydantic schema with response data
        :param session: Async database session
        :return: Created SurveyResponse instance
        """
        response = SurveyResponse(
            survey_id=response_data.survey_id,
            responder_slack_id=response_data.responder_slack_id,
            responder_name=response_data.responder_name,
            answer=response_data.answer,
            slack_id=response_data.responder_slack_id,  # Required by Base model
        )
        session.add(response)
        try:
            await session.commit()
            await session.refresh(response)
            return response
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error adding survey response: {e}")

    async def get_responses_by_survey(
        self, survey_id: int, session: AsyncSession
    ) -> list[SurveyResponse]:
        """
        Get all responses for a survey.

        :param survey_id: Survey ID to get responses for
        :param session: Async database session
        :return: List of SurveyResponse instances
        """
        query = select(SurveyResponse).filter(SurveyResponse.survey_id == survey_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def check_user_responded(
        self, survey_id: int, responder_slack_id: str, session: AsyncSession
    ) -> bool:
        """
        Check if a user has already responded to a survey.

        :param survey_id: Survey ID to check
        :param responder_slack_id: User's Slack ID
        :param session: Async database session
        :return: True if user has responded, False otherwise
        """
        query = select(SurveyResponse).filter(
            SurveyResponse.survey_id == survey_id,
            SurveyResponse.responder_slack_id == responder_slack_id,
        )
        result = await session.execute(query)
        return result.scalars().first() is not None


class SurveySentMessageCRUDManager(BaseCRUDManager):
    """
    CRUD manager for SurveySentMessage operations.
    """

    def __init__(self, model=None):
        self.model = model or SurveySentMessage

    async def add_sent_message(
        self, sent_data: SurveySentMessageCreate, session: AsyncSession
    ) -> SurveySentMessage:
        """
        Record a sent survey message.

        :param sent_data: Data for the sent message
        :param session: Async database session
        :return: Created SurveySentMessage instance
        """
        sent_msg = SurveySentMessage(
            survey_id=sent_data.survey_id,
            receiver_slack_id=sent_data.receiver_slack_id,
            message_ts=sent_data.message_ts,
            slack_id=sent_data.receiver_slack_id,  # Required by Base model
        )
        session.add(sent_msg)
        try:
            await session.commit()
            await session.refresh(sent_msg)
            return sent_msg
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error adding sent message record: {e}")

    async def get_sent_messages(
        self, survey_id: int, session: AsyncSession
    ) -> List[SurveySentMessage]:
        """
        Get all sent messages for a survey.

        :param survey_id: Survey ID
        :param session: Async database session
        :return: List of SurveySentMessage instances
        """
        query = select(SurveySentMessage).filter(
            SurveySentMessage.survey_id == survey_id
        )
        result = await session.execute(query)
        return list(result.scalars().all())


# Singleton instances for convenience
survey_manager = SurveyCRUDManager()
survey_response_manager = SurveyResponseCRUDManager()
survey_sent_message_manager = SurveySentMessageCRUDManager()
