from app.infrastructure.db.repositories import UsersRepository

class UserService:
    def __init__(self):
        self.repo = UsersRepository()

    def sync_user(self, slack_users: list[dict[str, str]]):
        self.repo.upsert_many(slack_users)

    def get_admins(self):
        return self.repo.list_admins()

    def get_ignored(self):
        return self.repo.list_ignored()