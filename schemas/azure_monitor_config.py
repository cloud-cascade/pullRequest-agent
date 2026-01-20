"""Azure Monitor observability configuration schema.

Following Microsoft Agent Framework documentation:
https://learn.microsoft.com/en-us/agent-framework/user-guide/observability
"""

import os
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureMonitorConfig(BaseSettings):
    """Azure Monitor observability configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Connection string - checks multiple env var names
    connection_string: Optional[str] = Field(
        None,
        description="Azure Application Insights connection string"
    )

    enable_sensitive_data: bool = Field(
        default=False,
        alias="ENABLE_SENSITIVE_DATA",
        description="Enable sensitive data (prompts/responses) in telemetry. Only use in dev/test."
    )

    @model_validator(mode='before')
    @classmethod
    def resolve_connection_string(cls, values):
        """Resolve connection string from multiple possible environment variables."""
        if 'connection_string' not in values or not values.get('connection_string'):
            # Try multiple env var names for connection string
            conn_str = (
                os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") or
                os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING") or
                os.getenv("AZURE_MONITOR_CONNECTION_STRING")
            )
            if conn_str:
                values['connection_string'] = conn_str
        return values

    def is_enabled(self) -> bool:
        """Check if observability is configured."""
        return bool(self.connection_string)
