from sqlalchemy.orm import Mapped, mapped_column

from shared.schemas.base_models import Base


class Slack_User(Base):
    username: Mapped[str]
    realname: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, index=True)
    is_deleted: Mapped[bool]
    is_ignore: Mapped[bool]


class Admin(Base):
    is_admin: Mapped[bool]
