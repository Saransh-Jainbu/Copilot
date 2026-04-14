"""
Tests for API Layer: Routes
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


class TestHealthEndpoint:
    """Test the /api/health endpoint."""

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data


class TestDebugEndpoint:
    """Test the /api/debug endpoint."""

    def test_debug_requires_log_text(self, client):
        response = client.post("/api/debug", json={})
        assert response.status_code == 422  # Validation error

    def test_debug_rejects_short_input(self, client):
        response = client.post("/api/debug", json={"log_text": "hi"})
        assert response.status_code == 422

    def test_debug_accepts_valid_input(self, client):
        """Integration test — requires HuggingFace API token.
        Skip if not available."""
        import os
        if not os.getenv("HUGGINGFACE_API_TOKEN"):
            pytest.skip("HUGGINGFACE_API_TOKEN not set")

        response = client.post(
            "/api/debug",
            json={
                "log_text": "ModuleNotFoundError: No module named 'numpy'\n##[error]Process completed with exit code 1.",
                "enable_rag": False,
                "enable_self_critique": False,
                "max_steps": 3,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "classification" in data
        assert "diagnosis" in data


class TestMetricsEndpoint:
    """Test the /api/metrics endpoint."""

    def test_metrics_endpoint(self, client):
        response = client.get("/api/metrics")
        assert response.status_code == 200
