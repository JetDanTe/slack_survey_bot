from sqlalchemy.orm import Mapped, mapped_column

from shared.schemas.base_models import Base


class Slack_User(Base):
    username: Mapped[str]
    realname: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, index=True)
    slack_id: Mapped[str]
    is_deleted: Mapped[bool]
    is_ignore: Mapped[bool]


class Admin(Base):
    slack_id: Mapped[str]
    is_admin: Mapped[bool]
