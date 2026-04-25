import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ['DATABASE_URL'] = 'sqlite:///./backend_test.db'

from app import app
from database import Base, get_db


@pytest.fixture(scope='session')
def test_db_url() -> str:
    db_path = Path(__file__).resolve().parents[1] / 'backend_test.db'
    return f"sqlite:///{db_path.as_posix()}"


@pytest.fixture(scope='session')
def engine(test_db_url: str):
    engine = create_engine(
        test_db_url,
        connect_args={'check_same_thread': False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope='function')
def db_session(engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope='function')
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
