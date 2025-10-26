from sqlalchemy import Column
from sqlalchemy import create_engine, Column, String, Boolean, MetaData, Table, insert, select
from app.infrastructure.db.connection import SessionLocal, engine, Base


class Users(Base):
    """
       User model representing the users table.
    """
    __tablename__ = 'users'

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    real_name = Column(String, nullable=False)
    is_deleted = Column(Boolean)
    is_admin = Column(Boolean, default=False)
    is_ignore = Column(Boolean, default=False)


class Surveys:
    """
    Surveys model representing the surveys table.
    """
    __tablename__ = 'surveys'

    id = Column(String, primary_key=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(String, nullable=False)