"""
User List models.

SQLAlchemy models for User Lists and their members, along with Pydantic schemas.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.schemas.base_models import Base
from shared.schemas.users import Slack_User

# =============================================================================
# SQLAlchemy Models
# =============================================================================


class UserList(Base):
    """
    User List table.

    Defines a named list of users that can be targeted by surveys.
    """

    __tablename__ = "user_lists"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship to members
    members: Mapped[list["UserListMember"]] = relationship(
        "UserListMember", back_populates="user_list", cascade="all, delete-orphan"
    )

    # # Relationship to surveys (M2M)
    # surveys: Mapped[list["Survey"]] = relationship(
    #     "Survey", secondary="survey_user_lists", back_populates="user_lists"
    # )


class UserListMember(Base):
    """
    User List Member table.

    Junction table mapping users to a User List.
    """

    __tablename__ = "user_list_members"

    user_list_id: Mapped[int] = mapped_column(
        ForeignKey("user_lists.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("slack_users.id"), nullable=False)

    # Relationship back to list
    user_list: Mapped["UserList"] = relationship("UserList", back_populates="members")
    # Relationship to user
    user: Mapped["Slack_User"] = relationship("Slack_User")

    __table_args__ = (
        UniqueConstraint("user_list_id", "user_id", name="uq_user_list_member"),
    )


# =============================================================================
# Pydantic Schemas
# =============================================================================


class UserListCreate(BaseModel):
    """Schema for creating a new user list."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class UserListRead(BaseModel):
    """Schema for reading user list data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: Optional[object] = None


class UserListMemberAdd(BaseModel):
    """Schema for adding a member to a list."""

    user_id: int = Field(..., description="ID of the user in slack_users table")


class UserListMemberRead(BaseModel):
    """Schema for reading list member data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_list_id: int
    user_id: int
