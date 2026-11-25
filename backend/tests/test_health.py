from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "OpenCampus API"
    assert body["version"] == "0.1.0"
    assert body["uptime_seconds"] >= 0
    datetime.fromisoformat(body["timestamp"])


def test_cors_allows_dev_frontend():
    response = client.get(
        "/api/health", headers={"Origin": "http://localhost:5173"}
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_route_is_404():
    assert client.get("/api/does-not-exist").status_code == 404
