from typing import Generic, TypeVar, Type
from sqlalchemy.orm import Session
from app.infrastructure.db.connection import SessionLocal
from app.infrastructure.db.models import Users, Surveys

T = TypeVar('T')

class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Session):
        self.model = model
        self.session = session

    def get(self, id_: int):
        return self.session.get(self.model, id_)

    def list(self):
        return self.session.query(self.model).all()

    def add(self, obj: T):
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, id_: int):
        obj = self.get(id_)
        if obj:
            self.session.delete(obj)
            self.session.commit()





class UsersRepository:
    def __init__(self, session: Session | None = None):
        self.session = session or SessionLocal()

    def list_admins(self):
        return self.session.query(Users).filter_by(is_admin=True).all()

    def list_ignored(self):
        return self.session.query(Users).filter_by(is_ignored=True).all()

    def upsert_many(self, users: list[dict[str, str]]):
        for user in users:
            if user.get('is_bot') or user.get('id') == 'USLACKBOT':
                continue
            existing = self.session.query(Users).filter_by(id=user['id']).first()
            if existing:
                existing.is_deleted = user.get('deleted')
            else:
                new = Users(
                    id=user['id'],
                    name=user['name'],
                    real_name=user.get('profile', {}).get('real_name', ''),
                    is_deleted=user.get('deleted', False),
                )
                self.session.add(new)
        self.session.commit()


class SurveysRepository(BaseRepository[Surveys]):
    def __init__(self):
        super().__init__(Surveys, SessionLocal())

    def list_recent(self, limit: int = 20):
        return (
            self.session.query(Surveys)
            .order_by(Surveys.created_at.desc())
            .limit(limit)
            .all()
        )