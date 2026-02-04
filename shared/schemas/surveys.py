"""
Survey and SurveyResponse models.

SQLAlchemy models for database tables and Pydantic schemas for validation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.schemas.base_models import Base

# =============================================================================
# SQLAlchemy Models (Database Tables)
# =============================================================================

survey_user_lists = Table(
    "survey_user_lists",
    Base.metadata,
    Column("survey_id", ForeignKey("surveys.id"), primary_key=True),
    Column("user_list_id", ForeignKey("user_lists.id"), primary_key=True),
)


class Survey(Base):
    """
    Survey metadata table.

    Stores survey information with owner details.
    """

    __tablename__ = "surveys"

    survey_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_slack_id: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    # user_lists: Mapped[list["UserList"]] = relationship(
    #     "UserList", secondary=survey_user_lists, back_populates="surveys"
    # )

    # Relationship to responses
    responses: Mapped[list["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="survey", cascade="all, delete-orphan"
    )


class SurveyResponse(Base):
    """
    Survey response table.

    Stores individual responses linked to a survey via foreign key.
    """

    __tablename__ = "survey_responses"

    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), nullable=False)
    responder_slack_id: Mapped[str] = mapped_column(String(50), nullable=False)
    responder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship back to survey
    survey: Mapped["Survey"] = relationship("Survey", back_populates="responses")


# =============================================================================
# Pydantic Schemas (Validation & Serialization)
# =============================================================================


class SurveyCreate(BaseModel):
    """Schema for creating a new survey."""

    survey_name: str = Field(..., min_length=1, max_length=255)
    owner_slack_id: str = Field(..., min_length=1, max_length=50)
    owner_name: str = Field(..., min_length=1, max_length=255)


class SurveyRead(BaseModel):
    """Schema for reading survey data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    survey_name: str
    owner_slack_id: str
    owner_name: str
    is_active: bool
    created_at: datetime
    slack_id: str
    # Note: user_list_ids not included by default to avoid complexity in fetching unless requested


class SurveyResponseCreate(BaseModel):
    """Schema for creating a new survey response."""

    survey_id: int
    responder_slack_id: str = Field(..., min_length=1, max_length=50)
    responder_name: str = Field(..., min_length=1, max_length=255)
    answer: str = Field(..., min_length=1)


class SurveyResponseRead(BaseModel):
    """Schema for reading survey response data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    survey_id: int
    responder_slack_id: str
    responder_name: str
    answer: str
    created_at: datetime
    slack_id: str
