"""
Survey CRUD Manager.

Provides async CRUD operations for Survey and SurveyResponse models.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.schemas.surveys import (
    Survey,
    SurveyCreate,
    SurveyResponse,
    SurveyResponseCreate,
)
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
            owner_slack_id=survey_data.owner_slack_id,
            owner_name=survey_data.owner_name,
            slack_id=survey_data.owner_slack_id,  # Required by Base model
            is_active=True,
        )
        session.add(survey)
        try:
            await session.commit()
            await session.refresh(survey)
            return survey
        except Exception as e:
            await session.rollback()
            raise Exception(f"Error creating survey: {e}")

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
        return result.scalar_one_or_none() is not None


# Singleton instances for convenience
survey_manager = SurveyCRUDManager()
survey_response_manager = SurveyResponseCRUDManager()
