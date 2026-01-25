"""Configuration management for Zoho automation agents."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Zoho API (Desk)
    zoho_client_id: str
    zoho_client_secret: str
    zoho_refresh_token: str
    zoho_datacenter: str = "com"

    # Zoho Desk
    zoho_desk_org_id: str

    # Zoho CRM (credentials séparées si nécessaire)
    zoho_crm_client_id: Optional[str] = None
    zoho_crm_client_secret: Optional[str] = None
    zoho_crm_refresh_token: Optional[str] = None

    # Anthropic
    anthropic_api_key: str

    # Agent configuration
    agent_model: str = "claude-sonnet-4-5-20250929"  # Claude Sonnet 4.5
    agent_max_tokens: int = 4096
    agent_temperature: float = 0.7

    # Logging
    log_level: str = "INFO"

    @property
    def zoho_accounts_url(self) -> str:
        """Get Zoho accounts URL based on datacenter."""
        return f"https://accounts.zoho.{self.zoho_datacenter}"

    @property
    def zoho_desk_api_url(self) -> str:
        """Get Zoho Desk API URL based on datacenter."""
        return f"https://desk.zoho.{self.zoho_datacenter}/api/v1"

    @property
    def zoho_crm_api_url(self) -> str:
        """Get Zoho CRM API URL based on datacenter."""
        return f"https://www.zohoapis.{self.zoho_datacenter}/crm/v3"


# Global settings instance
settings = Settings()
