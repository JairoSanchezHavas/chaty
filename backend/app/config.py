from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── LLM backend ───────────────────────────────────────────────────────────
    # "gemini"  → Google AI Studio (GEMINI_API_KEY)
    # "vertex"  → Vertex AI (ADC / GOOGLE_APPLICATION_CREDENTIALS)
    llm_backend: Literal["gemini", "vertex"] = "gemini"

    # Google AI Studio
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "gemini-embedding-001"

    # Vertex AI
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    vertex_chat_model: str = "gemini-2.5-flash"
    vertex_embed_model: str = "text-embedding-004"

    data_dir: Path = Path("./data")
    tenants_dir: Path = Path("./app/tenants")
    cors_origins: str = "*"

    # Google Calendar — Service Account
    google_sa_credentials_path: Path = Path("./secrets/gcal-sa.json")
    rep_calendar_id: str = ""
    rep_name: str = "Dra. Ana Villanueva"
    rep_email: str = ""
    timezone: str = "America/Mexico_City"

    @property
    def db_path(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return str(self.data_dir / "chaty.db")

    @property
    def checkpoints_path(self) -> str:
        return str(self.data_dir / "checkpoints.db")

    @property
    def chroma_path(self) -> str:
        path = self.data_dir / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def tenant_dir(self, tenant_id: str) -> Path:
        return self.tenants_dir / tenant_id

    @property
    def gcal_enabled(self) -> bool:
        return (
            self.google_sa_credentials_path.exists()
            and bool(self.rep_calendar_id)
        )


settings = Settings()
