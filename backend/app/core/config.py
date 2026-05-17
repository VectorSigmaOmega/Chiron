from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chiron Backend"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api"
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Allowed browser origins for the separate frontend dev server.",
    )
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{(Path(__file__).resolve().parents[2] / 'chiron.db').as_posix()}",
        description="Async database URL. Defaults to local SQLite for zero-manual-setup bootstrapping.",
    )
    llm_mode: str = Field(
        default="heuristic",
        description="heuristic or gemini. Heuristic mode keeps the scaffold runnable without API keys.",
    )
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3-flash-preview"
    gemini_query_model: str | None = None
    gemini_synthesis_model: str | None = None
    gemini_verifier_model: str | None = None
    literature_connector_mode: str = Field(
        default="mock",
        description="mock or pubmed. PubMed mode uses NCBI E-utilities for the literature specialist.",
    )
    trials_connector_mode: str = Field(
        default="mock",
        description="mock or clinicaltrials. ClinicalTrials mode uses the ClinicalTrials.gov v2 API.",
    )
    drug_safety_connector_mode: str = Field(
        default="mock",
        description="mock or dailymed. DailyMed mode uses the official DailyMed web services.",
    )
    guideline_connector_mode: str = Field(
        default="mock",
        description="mock or fixture. Fixture mode uses a curated local guideline dataset for the MVP.",
    )
    pubmed_base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    pubmed_api_key: str | None = None
    pubmed_tool: str = "chiron"
    pubmed_email: str | None = None
    pubmed_retmax: int = 5
    clinicaltrials_base_url: str = "https://clinicaltrials.gov/api/v2"
    clinicaltrials_page_size: int = 3
    dailymed_base_url: str = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
    dailymed_page_size: int = 3
    guideline_fixture_path: str = str(
        Path(__file__).resolve().parents[1] / "connectors" / "fixtures" / "guidelines.json"
    )
    max_iterations: int = 3
    max_specialist_tasks: int = 8
    max_schema_retries: int = 2

    model_config = SettingsConfigDict(
        env_prefix="CHIRON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
