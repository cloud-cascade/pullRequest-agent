"""Main configuration container for PR Agent."""

from typing import Optional

from pydantic import BaseModel, Field

from .github_config import GitHubConfig
from .azure_openai_config import AzureOpenAIConfig
from .azure_monitor_config import AzureMonitorConfig
from .pr_analysis_config import PRAnalysisConfig


class PRAgentConfig(BaseModel):
    """Main configuration container for PR Agent."""
    
    github: GitHubConfig
    azure_openai: AzureOpenAIConfig
    azure_monitor: Optional[AzureMonitorConfig] = None
    analysis: PRAnalysisConfig = Field(default_factory=PRAnalysisConfig)
    
    @classmethod
    def from_environment(cls) -> "PRAgentConfig":
        """Create configuration from environment variables.
        
        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # BaseSettings will automatically load from environment variables
        # and .env file based on model_config settings
        try:
            github_config = GitHubConfig()  # type: ignore
            azure_config = AzureOpenAIConfig()  # type: ignore
            monitor_config = AzureMonitorConfig()  # type: ignore
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}")
        
        return cls(
            github=github_config,
            azure_openai=azure_config,
            azure_monitor=monitor_config
        )
    
    def update_analysis_file_counts(self, total_files: int, relevant_files: int):
        """Update analysis configuration with file counts."""
        self.analysis.total_file_count = total_files
        self.analysis.relevant_file_count = relevant_files
        # Trigger validation to update truncation flag
        self.analysis = PRAnalysisConfig(**self.analysis.model_dump())
