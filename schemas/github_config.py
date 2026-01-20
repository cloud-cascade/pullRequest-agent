"""GitHub configuration schema with automatic validation."""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubConfig(BaseSettings):
    """GitHub configuration with automatic validation."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    github_token: str = Field(..., alias="GITHUB_TOKEN", description="GitHub API token")
    github_repository: str = Field(..., alias="GITHUB_REPOSITORY", description="Repository in owner/repo format")
    github_event_path: Optional[str] = Field(None, alias="GITHUB_EVENT_PATH", description="Path to GitHub event payload")
    pr_number: int = Field(..., description="Pull request number")  # Required after validation
    
    def __init__(self, **data):
        """Initialize with custom pr_number extraction logic."""
        # Extract pr_number from event path if not provided
        if 'pr_number' not in data or data['pr_number'] is None:
            pr_number_from_env = os.getenv("PR_NUMBER")
            if pr_number_from_env:
                data['pr_number'] = int(pr_number_from_env)
            elif 'github_event_path' in data and data['github_event_path']:
                event_path = Path(data['github_event_path'])
                if event_path.exists():
                    try:
                        with open(event_path, 'r') as f:
                            event_data = json.load(f)
                            extracted_pr = event_data.get("pull_request", {}).get("number")
                            if extracted_pr:
                                data['pr_number'] = extracted_pr
                    except (json.JSONDecodeError, IOError):
                        pass
        
        super().__init__(**data)
    
    @field_validator('pr_number')
    @classmethod
    def validate_pr_number(cls, v: Optional[int]) -> int:
        """Ensure PR number is provided."""
        if v is None:
            raise ValueError(
                "Could not determine PR number from event payload or PR_NUMBER env var"
            )
        return v
    
    @field_validator('github_repository')
    @classmethod
    def validate_repository_format(cls, v: str) -> str:
        """Validate repository is in owner/repo format.
        
        If a full GitHub URL is provided, extract the owner/repo from it.
        """
        import re
        
        # If it's a full GitHub URL, extract owner/repo
        if v.startswith('http://') or v.startswith('https://'):
            # Match patterns like:
            # https://github.com/owner/repo
            # https://github.com/owner/repo/pull/123
            match = re.search(r'github\.com/([^/]+/[^/]+)', v)
            if match:
                v = match.group(1)
            else:
                raise ValueError(
                    f"Could not extract owner/repo from GitHub URL: {v}. "
                    "Expected format: 'owner/repo' or 'https://github.com/owner/repo'"
                )
        
        # Validate it's in owner/repo format
        if '/' not in v:
            raise ValueError("GITHUB_REPOSITORY must be in 'owner/repo' format")
        
        # Remove any trailing path components
        parts = v.split('/')
        if len(parts) > 2:
            v = f"{parts[0]}/{parts[1]}"
        
        return v
