from sqlalchemy import create_engine, Column, String, Boolean, MetaData, Table, insert, select
from sqlalchemy.orm import declarative_base, sessionmaker
from custom_exceptions import EnvironmentVarException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import exists
import typing as tp
import os


class DatabaseConfig:
    """
    Manage database configuration and connection setup.
    """
    REQUIRED_VARS = ('POSTGRES_HOST', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB')

    @classmethod
    def validate_environment(cls) -> tp.Dict[str, str]:
        """
        Validate and retrieve database environment variables.

        :return: Dictionary of database configuration variables
        :raises EnvironmentVarException: If variables are missing or empty
        """
        config = {}
        for env_var in cls.REQUIRED_VARS:
            value = os.environ.get(env_var)
            print(f"{env_var}: {value}")
            if not value:
                raise EnvironmentVarException(f'Environment variable "{env_var}" is missing or empty')
            config[env_var] = value
        return config

    @classmethod
    def get_database_url(cls, config: tp.Dict[str, str]) -> str:
        """
        Generate database URL from configuration.

        :param config: Database configuration dictionary
        :return: SQLAlchemy database connection URL
        """
        return (
            f'postgresql://{config["POSTGRES_USER"]}:'
            f'{config["POSTGRES_PASSWORD"]}@'
            f'{config["POSTGRES_HOST"]}/'
            f'{config["POSTGRES_DB"]}'
        )


class DataBaseManager:
    """
    Manages database operations and user-related queries
    """

    def __init__(self, database_url):
        """
        Initialize database engine and session.

        :param database_url: SQLAlchemy database connection URL
        """
        self.engine = create_engine(database_url, echo=False)
        self.Base = declarative_base()
        self.Session = sessionmaker(bind=self.engine)

    class User(declarative_base()):
        """
        User model representing the users table.
        """
        __tablename__ = 'users'

        id = Column(String, primary_key=True, nullable=False)
        name = Column(String, nullable=False)
        real_name = Column(String, nullable=False)
        is_deleted = Column(Boolean)
        is_admin = Column(Boolean, default=False)
        is_ignore = Column(Boolean, default=False)

    def create_table(self) -> None:
        """Create all defined table in database."""
        self.Base.metadata.create_all(self.engine)

    def drop_tables(self) -> None:
        """Drop all tables in the database."""
        self.Base.metadata.drop_all(self.engine)

    def create_audit_table(self, audit_name: str) -> None:
        """
        Create a new audit table.

        :param audit_name: Name of the audit table
        :return: Create SQLAlchemy Table object
        """
        metadata = MetaData()
        audit_table = Table(
            audit_name, metadata,
            Column('id', String, primary_key=True, nullable=False),
            Column('name', String, nullable=False),
            Column('answer', String, nullable=False)
        )
        audit_table.create(self.engine)

    def update_users(
            self,
            users: tp.List[tp.Dict],
            to_admin: bool = False,
            to_ignore: bool = False,
            by_name: bool = False,
    ) -> tp.List[str]:
        """
        Update user information in the database.

        :param users: List of user data
        :param to_admin: Toggle admin status
        :param to_ignore: Toggle ignore status
        :param by_name: Update by username instead of ID
        :return: List of not found users
        """

        not_found_users = []
        with self.Session() as session:
            try:
                for user in users:
                    if by_name:
                        not_found_users.extend(
                            self._update_user_by_name(session, user, to_admin, to_ignore)
                        )
                    else:
                        not_found_users.extend(
                            self._update_or_create_user(session, user)
                        )
                session.commit()
            except SQLAlchemyError as e:
                session.rollback()
                raise
        return not_found_users

    def _update_user_by_name(
            self,
            session,
            user: dict,
            to_admin: bool,
            to_ignore: bool
    ) -> tp.List[tp.Dict]:
        """
        Update user status by username.

        :param session: SQLAlchemy session
        :param user: Username
        :param to_admin: Toggle admin status
        :param to_ignore: Toggle ignore status
        :return: List of not found users
        """
        not_found_users = []
        existing_user = session.query(self.User).filter_by(name=user.get('name')).first()

        if existing_user:
            if to_ignore:
                existing_user.is_ignore = not existing_user.is_ignore
            if to_admin:
                existing_user.is_admin = not existing_user.is_admin
        else:
            not_found_users.append(user)

        return not_found_users

    def _update_or_create_user(
            self,
            session,
            user: tp.Dict
    ) -> tp.List[str]:
        """
        Update existing user or create new user.

        :param session: SQLAlchemy session
        :param user: User data dictionary
        :return: List of not found users
        """
        if user.get('is_bot') or user.get('id') == 'USLACKBOT':
            return []

        new_db_user = self.User(
            id=user.get('id'),
            name=user.get('name'),
            real_name=user.get('profile', {}).get('real_name', ''),
            is_deleted=user.get('deleted', False)
        )

        existing_user = session.query(self.User).filter_by(id=new_db_user.id).first()

        if existing_user:
            if existing_user.is_deleted != new_db_user.is_deleted:
                existing_user.is_deleted = new_db_user.is_deleted
                print(f"User '{new_db_user.name}' found. Updating is_deleted to {new_db_user.is_deleted}.")
        else:
            session.add(new_db_user)

        return []

    def get_users(
            self,
            command_name: str,
            second_table: str = None
    ) -> tp.Union[tp.List[tp.Type[User]], str]:
        """
        Retrieve users based on different criteria.

        :param command_name: Type of user query
        :param second_table: Secondary table name for specific queries
        :return: List of users or error message
        """
        second_table = self.check_table_exists(second_table)
        with self.Session() as session:
            if command_name == '/ignore_show':
                return session.query(self.User).filter_by(is_ignore=True).all()

            elif command_name == '/admin_show':
                return session.query(self.User).filter_by(is_admin=True).all()

            # elif command_name == '/audit_stop':
            #     return session.query(second_table)

            elif command_name == '/audit_unanswered':
                return (
                    session.query(self.User)
                    .filter_by(is_deleted=False)
                    .filter_by(is_ignore=False)
                    .filter(~exists().where(second_table.c.id == self.User.id))
                    .all()
                )

        return "Unknown setup."

    def check_table_exists(self, table_name: str) -> tp.Optional[Table]:
        """
        Check if a table exists in the database.

        :param table_name: Name of the table to check
        :return: Table object if exists, None otherwise
        """
        metadata = MetaData()
        metadata.reflect(bind=self.engine)
        return metadata.tables.get(table_name)

    def add_row(self, table: str, data: tp.Dict) -> None:
        """
        Add a row to a specific table.

        :param table: SQLAlchemy Table object
        :param data: Dictionary of row data
        """
        table = self.check_table_exists(table)
        with self.engine.connect() as conn:
            inserting = insert(table).values(data)
            conn.execute(inserting)
            conn.commit()

    def select_table(self, table: str):
        """
        Select all rows from a table.

        :param table: SQLAlchemy Table object
        :return: Query result
        """
        table = self.check_table_exists(table)
        with self.engine.connect() as connection:
            table_obj = select(table)
            return connection.execute(table_obj)

    def check_if_answer_exist(self, data: tp.Dict) -> tp.Any:
        """Check if answer for same user exist

        :para data: Dict with answer data: user, id, answer
        :return Bool: True or False if answer exist
        """
        return self.Session().query(exists().where(self.User.id == data.get('id'))).scalar()


def database_init() -> DataBaseManager:
    """
    Initialize database configuration and manager.

    :return: Configured DatabaseManager instance
    """
    config = DatabaseConfig.validate_environment()
    database_url = DatabaseConfig.get_database_url(config)
    return DataBaseManager(database_url)


