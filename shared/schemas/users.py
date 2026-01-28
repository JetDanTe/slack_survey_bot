from sqlalchemy.orm import Mapped

from shared.schemas.base_models import Base


class Slack_User(Base):
    username: Mapped[str]
    realname: Mapped[str]
    is_deleted: Mapped[bool]
    is_ignore: Mapped[bool]


class Admin(Base):
    is_admin: Mapped[bool]
