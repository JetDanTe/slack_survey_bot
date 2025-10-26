from app.infrastructure.db.repositories import UsersRepository
from app.infrastructure.db.connection import Base, engine
from app.infrastructure.db.connection import create_all, drop_all
from typing import Iterable, Optional


class DatabaseManager:

    def __init__(self):
        self.users_repo = UsersRepository()

    def create_all(self):
        Base.metadata.create_all(engine)

    def drop_all(self):
        Base.metadata.drop_all(engine)

    def get_users(self, command_name: str):
        if command_name == '/admin_show':
            return self.users_repo.list_admin()
        elif command_name == '/ignore_show':
            return self.users_repo.list_ignored()
        else:
            return []

    def update_users(
            self,
            users: Iterable[dict],
            to_admin: bool = False,
            to_ignore: bool = False,
            by_name: bool = False,
    ) -> list[dict]:
        if by_name:
            names = [u.get('name') for u in users if u.get('name')]
            return self.users_repo.toggle_by_names(
                names=names, to_admin=to_admin, to_ignore=to_ignore
            )
        return self.users_repo.upsert_users(users)

