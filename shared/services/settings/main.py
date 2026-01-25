from functools import lru_cache

from pydantic_settings import BaseSettings


class CoreSettings(BaseSettings):
    APP_NAME: str
    DEBUG: bool = False


class PostgresSettings(BaseSettings):
    PGHOST: str
    PGDATABASE: str
    PGUSER: str
    PGPASSWORD: str
    PGPORT: int = 5432

    @property
    def DATABASE_ASYNC_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.PGUSER}:{self.PGPASSWORD}@"
            f"{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
        )

    @property
    def DATABASE_URL(self) -> str:
        """
        Generate database URL from configuration.

        :return: SQLAlchemy database connection URL
        """
        return (
            f"postgresql://{self.PGUSER}:"
            f"{self.PGPASSWORD}@"
            f"{self.PGHOST}:"
            f"{self.PGPORT}/"
            f"{self.PGDATABASE}"
        )


class SlackSettings(BaseSettings):
    SLACK_BOT_TOKEN: str
    SLACK_APP_TOKEN: str
    SLACK_ADMIN_ID: str
    SLACK_ADMIN_NAME: str


class Settings(CoreSettings, PostgresSettings, SlackSettings):
    pass


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
