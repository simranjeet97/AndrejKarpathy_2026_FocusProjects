from fastapi.testclient import TestClient
from evalops.api import app, get_storage

client = TestClient(app)

def test_api_health(temp_db_path):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert "ollama" in data
    assert "db" in data


def test_api_create_list_tasks(temp_db_path):
    # Create task
    payload = {
        "name": "Add numbers",
        "input_prompt": "What is 2+2?",
        "expected_output": "4",
        "tags": ["math", "simple"]
    }
    create_resp = client.post("/tasks", json=payload)
    assert create_resp.status_code == 200
    create_data = create_resp.json()
    assert "id" in create_data
    assert create_data["name"] == "Add numbers"

    # List tasks
    list_resp = client.get("/tasks")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) >= 1
    assert any(t["name"] == "Add numbers" for t in list_data)

    # Filter tasks by tag
    list_filtered = client.get("/tasks?tags=math")
    assert list_filtered.status_code == 200
    assert len(list_filtered.json()) >= 1


def test_api_submit_feedback(temp_db_path):
    payload = {
        "run_id": "run-batch-123",
        "task_id": "task-abc",
        "rating": 4,
        "notes": "Good output format."
    }
    response = client.post("/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["run_id"] == "run-batch-123"
    assert data["rating"] == 4
    assert data["notes"] == "Good output format."


def test_api_dashboard(temp_db_path):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

