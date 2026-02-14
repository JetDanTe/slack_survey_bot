from shared.schemas.surveys import (
    Survey,
    SurveyCreate,
    SurveyResponse,
    SurveyResponseCreate,
)
from shared.services.database.core.session import async_session_maker
from shared.services.database.surveys.crud import (
    survey_manager,
    survey_response_manager,
)


class SurveyHandler:
    async def create_survey(
        self, survey_name: str, survey_text: str, owner_slack_id: str, owner_name: str
    ) -> Survey:
        async with async_session_maker() as session:
            survey_data = SurveyCreate(
                survey_name=survey_name,
                survey_text=survey_text,
                owner_slack_id=owner_slack_id,
                owner_name=owner_name,
            )
            survey = await survey_manager.create_survey(
                survey_data=survey_data, session=session
            )
            return survey

    async def add_survey_response(
        self, survey_id: int, respondent_slack_id: str, responses: str
    ) -> SurveyResponse:
        async with async_session_maker() as session:
            survey_response_data = SurveyResponseCreate(
                survey_id=survey_id,
                responder_slack_id=respondent_slack_id,
                responder_name="Nit empty name",
                answer=str(responses),
            )
            survey_response = await survey_response_manager.add_response(
                response_data=survey_response_data, session=session
            )
            return survey_response

    async def get_all_surveys(self) -> list[Survey]:
        async with async_session_maker() as session:
            surveys = await survey_manager.get_all_surveys(session=session)
            return surveys

    async def get_active_surveys(self) -> list[Survey]:
        async with async_session_maker() as session:
            return await survey_manager.get_active_surveys(session=session)

    async def close_survey(self, survey_id: int) -> Survey:
        async with async_session_maker() as session:
            return await survey_manager.close_survey(
                survey_id=survey_id, session=session
            )
