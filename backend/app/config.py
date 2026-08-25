"""
Configuration module - loads environment variables and app settings
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """App settings loaded from .env file"""

    # Database
    database_url: str = "sqlite:///./ai_trace.db"

    # API Keys (for calling external LLM providers)
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""

    # Our OWN API's access control (optional - blank disables auth entirely,
    # which is convenient for local development)
    api_key: str = ""
    rate_limit_per_minute: int = 30

    # Environment
    environment: str = "development"
    debug: bool = True

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    reload: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    def is_production(self) -> bool:
        return self.environment == "production"

    def auth_enabled(self) -> bool:
        """Auth is OFF by default (empty api_key) so local dev just works."""
        return bool(self.api_key.strip())


settings = Settings()