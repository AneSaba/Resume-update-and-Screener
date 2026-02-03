"""Configuration management using Pydantic Settings."""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API Configuration
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    claude_model: str = Field(
        default="claude-opus-4-5-20251101",
        description="Claude model to use for resume tailoring"
    )
    max_tokens: int = Field(default=4096, description="Maximum tokens for API calls")

    # Project Paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent,
        description="Project root directory"
    )

    @property
    def data_dir(self) -> Path:
        """Data directory path."""
        return self.project_root / "data"

    @property
    def output_dir(self) -> Path:
        """Output directory path."""
        return self.project_root / "output"

    @property
    def templates_dir(self) -> Path:
        """Templates directory path."""
        return self.project_root / "src" / "templates"

    @property
    def resume_source_path(self) -> Path:
        """Resume source YAML file path."""
        return self.data_dir / "resume_source.yaml"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
