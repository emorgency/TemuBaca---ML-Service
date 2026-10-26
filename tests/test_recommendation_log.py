"""Recommendation requests log counts, never what the reader sent or got back (ML-T08)."""

import logging

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_TOKEN


client = TestClient(app, headers={"X-Internal-Token": TEST_TOKEN})


def logged(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "app.recommendations"]


def test_book_request_logs_counts_only(caplog):
    with caplog.at_level(logging.INFO, logger="app.recommendations"):
        body = client.post("/api/recommendations/books", json={"user_interests": ["Romansa", "Robot Luar Angkasa"], "top_n": 3}).json()

    [line] = logged(caplog)
    assert line.startswith("recommend kind=books model=")
    assert "interests=2 unmatched=1 results=3" in line and "latency_ms=" in line
    for private in ["romansa", "robot", *(item["book_id"] for item in body["recommendations"])]:
        assert private not in line.lower()


def test_community_request_never_logs_the_region(caplog):
    with caplog.at_level(logging.INFO, logger="app.recommendations"):
        body = client.post("/api/recommendations/communities", json={"user_interests": ["Puisi"], "user_region_code": "36.74", "top_n": 3}).json()

    [line] = logged(caplog)
    assert "kind=communities" in line and f"results={len(body['recommendations'])}" in line and "sources=-" in line
    for private in ["36.74", "tangerang", "puisi", *(item["community_id"] for item in body["recommendations"])]:
        assert private not in line.lower()


def test_community_request_logs_its_notice(caplog):
    with caplog.at_level(logging.INFO, logger="app.recommendations"):
        client.post("/api/recommendations/communities", json={"user_interests": ["Robot Luar Angkasa"], "top_n": 3})

    [line] = logged(caplog)
    assert "results=0" in line and "notice=NO_MATCH" in line
