"""Train a model from a synthetic snapshot before any app module loads.

Tests never read the production model in models/, so they do not change
when the TemuBaca catalog is retrained.
"""

import json
import os
import tempfile

from pathlib import Path


FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_small.json"

_model_dir = Path(tempfile.mkdtemp(prefix="temubaca-ml-test-"))
os.environ["MODEL_DIR"] = str(_model_dir)

from app.training import train  # noqa: E402

train(json.loads(FIXTURE.read_text(encoding="utf-8")), _model_dir)
