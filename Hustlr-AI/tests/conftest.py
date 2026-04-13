import os
import sys
import pytest

# Add the project root to sys.path so 'main' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from database import get_db
from unittest.mock import MagicMock, patch

# Mock database engine
DB_URL_MOCK = "sqlite:///./test.db"
engine = create_engine(DB_URL_MOCK, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    # Use MagicMock for DB session to avoid real DB dependency for route logic tests
    session = MagicMock()
    yield session

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_llm():
    with patch("services.ai_service.llm") as mock:
        yield mock

@pytest.fixture
def mock_vector_db():
    with patch("services.ai_service.vector_db") as mock:
        yield mock

@pytest.fixture
def mock_redis():
    with patch("routers.search_router.redis_client") as mock:
        yield mock
