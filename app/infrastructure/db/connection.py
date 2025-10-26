from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

Base = declarative_base()

def get_engine():
    url = (
        f'postgresql://{os.environ["POSTGRES_USER"]}:'
        f'{os.environ["POSTGRES_PASSWORD"]}@'
        f'{os.environ["POSTGRES_HOST"]}/'
        f'{os.environ["POSTGRES_DB"]}'
    )
    return create_engine(url, echo=False)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine)