"""Train a model from a synthetic snapshot before any app module loads.

Tests never read the production model in models/, so they do not change
when the TemuBaca catalog is retrained.
"""

import json
import os
import secrets
import tempfile

from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_small.json"

_model_dir = Path(tempfile.mkdtemp(prefix="temubaca-ml-test-"))
os.environ["MODEL_DIR"] = str(_model_dir)

# Random per run; API tests send it as X-Internal-Token.
TEST_TOKEN = secrets.token_hex(32)
os.environ["INTERNAL_TOKEN"] = TEST_TOKEN

from app.training import train  # noqa: E402

train(json.loads(FIXTURE.read_text(encoding="utf-8")), _model_dir)
