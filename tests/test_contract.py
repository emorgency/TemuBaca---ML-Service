"""Frozen request/response pairs shared with the website (ML-T10).

Each file in tests/contract/ holds one request the website sends and the exact
reply this service gives for the test fixtures (the snapshot in conftest.py and
tests/fixtures/small_graph). The website keeps byte-identical copies in
tests/fixtures/ml-contract/ and checks that src/lib/ml sends the same body and
parses the same reply, so a change on either side fails a test.

After an intended contract change, rewrite the files and copy them over:

    UPDATE_CONTRACT=1 pytest tests/test_contract.py
    cp tests/contract/*.json ../temubaca/tests/fixtures/ml-contract/
"""

import json
import os

from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from app.main import app
from app.routing.graph import load_graph
from app.routing.service import RoutePlanner
from tests.conftest import TEST_TOKEN


CONTRACT = Path(__file__).parent / "contract"
GRAPH = Path(__file__).parent / "fixtures" / "small_graph"
client = TestClient(app, headers={"X-Internal-Token": TEST_TOKEN})

# name -> (path, request body). Bodies match what the website's src/lib/ml sends.
CASES = {
    "books": ("/api/recommendations/books", {"user_interests": ["Romansa", "Robot Luar Angkasa"], "top_n": 3}),
    "communities": ("/api/recommendations/communities", {"user_interests": ["Puisi"], "user_region_code": "36.74", "top_n": 3}),
    "communities-no-match": ("/api/recommendations/communities", {"user_interests": ["Robot Luar Angkasa"], "top_n": 3}),
    "route": ("/api/routing/route", {"origin": {"lat": -6.19, "lng": 106.83}, "destination": {"lat": -6.192, "lng": 106.832}, "mode": "drive"}),
    "route-out-of-coverage": ("/api/routing/route", {"origin": {"lat": -6.19, "lng": 106.83}, "destination": {"lat": -6.9175, "lng": 107.6191}, "mode": "drive"}),
}


@pytest.fixture(autouse=True)
def fixture_graph():
    app.state.routing = RoutePlanner({"drive": load_graph(GRAPH)}, snap_max_m=300, cache_size=0)
    yield
    del app.state.routing


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize("name", sorted(CASES))
def test_reply_matches_the_frozen_contract(name):
    path, request = CASES[name]
    response = client.post(path, json=request)
    actual = {"path": path, "request": request, "status": response.status_code, "response": response.json()}
    file = CONTRACT / f"{name}.json"

    if os.environ.get("UPDATE_CONTRACT"):
        file.write_text(dump(actual), encoding="utf-8")
    assert file.read_text(encoding="utf-8") == dump(actual), f"{file.name} changed; see this module's docstring"


def test_every_contract_file_has_a_case():
    assert {file.stem for file in CONTRACT.glob("*.json")} == set(CASES)
