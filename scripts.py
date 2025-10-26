from app.infrastructure.db.connection import Base, engine



if __name__ == '__main__':
    Base.metadata.create_all(engine)
    print("Database initialized")
