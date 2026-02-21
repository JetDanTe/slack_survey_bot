"""
Survey and SurveyResponse models.

SQLAlchemy models for database tables and Pydantic schemas for validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table, Text
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
    survey_text: Mapped[str] = mapped_column(Text, server_default="")
    owner_slack_id: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    users_incl: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    users_excl: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reminder_interval_hours: Mapped[float] = mapped_column(Float, default=0)
    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    reminders_sent_count: Mapped[int] = mapped_column(Integer, default=0)

    responses: Mapped[list["SurveyResponse"]] = relationship(
        "SurveyResponse", back_populates="survey", cascade="all, delete-orphan"
    )

    sent_messages: Mapped[list["SurveySentMessage"]] = relationship(
        "SurveySentMessage", back_populates="survey", cascade="all, delete-orphan"
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


class SurveySentMessage(Base):
    """
    Track sent survey messages to allow deletion.
    """

    __tablename__ = "survey_sent_messages"

    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), nullable=False)
    receiver_slack_id: Mapped[str] = mapped_column(String(50), nullable=False)
    message_ts: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationship back to survey (optional but good for cascade delete)
    survey: Mapped["Survey"] = relationship("Survey", back_populates="sent_messages")


# =============================================================================
# Pydantic Schemas (Validation & Serialization)
# =============================================================================


class SurveyCreate(BaseModel):
    """Schema for creating a new survey."""

    survey_name: str = Field(..., min_length=1, max_length=255)
    survey_text: str = Field(..., min_length=1)
    owner_slack_id: str = Field(..., min_length=1, max_length=50)
    owner_name: str = Field(..., min_length=1, max_length=255)
    users_incl: Optional[str] = None
    users_excl: Optional[str] = None
    reminder_interval_hours: float = Field(default=0, ge=0)


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
    users_incl: Optional[str] = None
    users_excl: Optional[str] = None
    reminder_interval_hours: float = 0
    last_reminder_sent_at: Optional[datetime] = None
    reminders_sent_count: int = 0


class SurveyResponseCreate(BaseModel):
    """Schema for creating a new survey response."""

    survey_id: int
    responder_slack_id: str = Field(..., min_length=1, max_length=50)
    responder_name: str = Field(..., min_length=1, max_length=255)
    answer: str = Field(..., min_length=1)


class SurveySentMessageCreate(BaseModel):
    """Schema for creating a sent message record."""

    survey_id: int
    receiver_slack_id: str
    message_ts: str


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
