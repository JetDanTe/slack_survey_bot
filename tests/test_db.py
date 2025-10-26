from app.infrastructure.db.repositories import UsersRepository

def test_can_initialize_and_upsert():
    repo = UsersRepository()
    assert repo is not None
