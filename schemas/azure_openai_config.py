"""Azure OpenAI configuration schema with automatic validation and fallbacks."""

import os

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureOpenAIConfig(BaseSettings):
    """Azure OpenAI configuration with automatic validation and fallbacks."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    azure_openai_endpoint: str = Field(..., alias="AZURE_OPENAI_ENDPOINT", description="Azure OpenAI endpoint URL")
    azure_openai_api_key: str = Field(..., alias="AZURE_OPENAI_API_KEY", description="Azure OpenAI API key")
    deployment_name: str = Field(default="gpt-4o", description="Azure OpenAI deployment name")
    api_version: str = Field(default="2024-02-15-preview", alias="AZURE_OPENAI_API_VERSION", description="Azure OpenAI API version")
    
    @model_validator(mode='before')
    @classmethod
    def resolve_deployment_name(cls, values):
        """Resolve deployment name from multiple possible environment variables."""
        if 'deployment_name' not in values or not values.get('deployment_name'):
            # Try multiple env var names for deployment
            deployment_name = (
                os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME") or
                os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or
                "gpt-4o"
            )
            values['deployment_name'] = deployment_name
        return values
