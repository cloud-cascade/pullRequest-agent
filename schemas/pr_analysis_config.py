"""PR Analysis configuration schema with defaults and validation."""

from pydantic import BaseModel, Field, model_validator


class PRAnalysisConfig(BaseModel):
    """PR Analysis configuration with defaults and validation."""
    
    max_files_to_analyze: int = Field(
        default=50,
        gt=0,
        le=200,
        description="Maximum number of files to analyze (prevents token overflow)"
    )
    
    files_truncated: bool = Field(
        default=False,
        description="Whether files were truncated due to max limit"
    )
    
    relevant_file_count: int = Field(default=0, ge=0)
    total_file_count: int = Field(default=0, ge=0)
    
    @model_validator(mode='after')
    def check_truncation(self):
        """Automatically set files_truncated flag if limit exceeded."""
        if self.relevant_file_count > self.max_files_to_analyze:
            self.files_truncated = True
        return self
    
    def should_truncate_files(self) -> bool:
        """Check if files need to be truncated."""
        return self.relevant_file_count > self.max_files_to_analyze
    
    def get_file_slice_limit(self) -> int:
        """Get the limit for file slicing."""
        return min(self.relevant_file_count, self.max_files_to_analyze)
