import pytest
from services.ai_service import is_greeting, extract_radius
from unittest.mock import MagicMock, patch

def test_is_greeting_positive():
    assert is_greeting("hello") == True
    # assert is_greeting("Hii there!") == True
    assert is_greeting("Howdy") == True

def test_is_greeting_negative():
    assert is_greeting("I want a worker") == False
    assert is_greeting("hello provide me a cleaner") == False
    assert is_greeting("find workers within 5km") == False

def test_extract_radius_regex():
    assert extract_radius("Find workers within 10km") == 10
    assert extract_radius("Need a cleaner around 5 km") == 5
    assert extract_radius("15 kilometer search") == 15

@patch("services.ai_service.llm")
def test_extract_radius_llm_fallback(mock_llm):
    # Mock LLM response for non-regex query
    mock_llm.invoke.return_value.content = "50"
    assert extract_radius("Show me workers nearby") == 50
    mock_llm.invoke.assert_called_once()

def test_search_workers_employer_flow(client, db_session, mock_llm, mock_redis):
    # Setup mocks
    mock_redis.get.return_value = "employer"
    mock_llm.invoke.return_value.content = "I found 2 workers..."
    
    # Mock DB response for location
    db_session.execute.return_value.fetchone.return_value = (10.0, 20.0) # lat, lng
    
    # Mock search_workers_service return value directly to test endpoint routing
    # Or mock the internal service calls. Let's mock the helper calls.
    with patch("services.search_service.employer_helper.fetch_workers_for_employer") as mock_helper:
        mock_helper.return_value = (
            [{"name": "Worker 1"}, {"name": "Worker 2"}], # items_metadata
            ["Context 1", "Context 2"] # final_matches
        )
        
        response = client.get("/search", params={"query": "plumber", "user_id": 1, "role": "employer"})
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["workers_in_range_count"] == 2
        assert len(data["workers"]) == 2

def test_search_workers_worker_flow(client, db_session, mock_llm, mock_redis):
    mock_redis.get.return_value = "worker"
    mock_llm.invoke.return_value.content = "I found 3 jobs..."
    
    db_session.execute.return_value.fetchone.return_value = (10.0, 20.0)
    
    with patch("services.search_service.worker_helper.fetch_jobs_for_worker") as mock_helper:
        mock_helper.return_value = (
            [{"title": "Job 1"}, {"title": "Job 2"}, {"title": "Job 3"}],
            ["Job Context 1", "Job Context 2"]
        )
        
        response = client.get("/search", params={"query": "cleaning", "user_id": 2, "role": "worker"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["workers_in_range_count"] == 3
        assert len(data["jobs"]) == 3

def test_search_no_location_error(client, db_session):
    db_session.execute.return_value.fetchone.return_value = None
    
    response = client.get("/search", params={"query": "help", "user_id": 999, "role": "worker"})
    
    assert response.status_code == 404
    assert response.json()["detail"] == "User Location not found."
