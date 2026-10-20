from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Service settings read from the environment (and `.env` when present)."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    model_dir: Path = Path("models")
    graph_dir: Path = Path("data/graphs")
    routing_graphs: str = ""
    snap_max_m: float = 300
    route_cache_size: int = 1000
    internal_token: str = ""

    @field_validator("internal_token")
    @classmethod
    def long_enough_token(cls, token):
        token = token.strip()
        if token and len(token) < 32:
            raise ValueError("INTERNAL_TOKEN must be at least 32 characters")
        return token

    @property
    def model_path(self) -> Path:
        """Absolute model directory; relative values resolve from the repo root."""
        if self.model_dir.is_absolute():
            return self.model_dir
        return BASE_DIR / self.model_dir

    @property
    def graph_path(self) -> Path:
        """Absolute graph directory; relative values resolve from the repo root."""
        if self.graph_dir.is_absolute():
            return self.graph_dir
        return BASE_DIR / self.graph_dir


settings = Settings()
