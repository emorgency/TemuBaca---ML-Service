"""R-07 internal token, body limit, CORS, and /health (ML-T07, ML-T08)."""

import pytest

from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.main import app
from tests.conftest import TEST_TOKEN


anonymous = TestClient(app)
BOOKS = "/api/recommendations/books"
COMMUNITIES = "/api/recommendations/communities"


@pytest.mark.parametrize("path", [BOOKS, COMMUNITIES])
def test_api_requires_the_token(path):
    assert anonymous.post(path, json={}).status_code == 401
    assert anonymous.post(path, json={}, headers={"X-Internal-Token": "x" * 64}).status_code == 401
    assert anonymous.post(path, json={}, headers={"X-Internal-Token": TEST_TOKEN}).status_code == 200


def test_unconfigured_token_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "internal_token", "")

    response = anonymous.post(BOOKS, json={}, headers={"X-Internal-Token": TEST_TOKEN})

    assert response.status_code == 503


def test_short_token_is_rejected_at_startup():
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(internal_token="too-short")


def test_large_bodies_are_rejected_before_auth():
    body = '{"user_interests": ["' + "x" * 9000 + '"]}'

    declared = anonymous.post(BOOKS, content=body, headers={"content-type": "application/json"})
    streamed = anonymous.post(
        BOOKS,
        content=iter([body.encode()]),
        headers={"content-type": "application/json", "X-Internal-Token": TEST_TOKEN},
    )

    assert declared.status_code == 413
    assert streamed.status_code == 413


def test_no_cors_headers():
    response = anonymous.options(
        BOOKS,
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_health_is_open_and_reports_the_model():
    body = anonymous.get("/health").json()

    assert body["status"] == "ok"
    assert body["service"] == "temubaca-ml"
    assert body["model_version"].startswith("temubaca-")
    assert body["book_count"] == 24
