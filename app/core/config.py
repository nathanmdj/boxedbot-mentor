"""
Application configuration using Pydantic settings
"""

import os
from typing import List, Optional
from pydantic import validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # App settings
    APP_NAME: str = "boxedbot"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    
    # API settings
    API_PREFIX: str = "/api/v1"
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # GitHub App settings
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_API_URL: str = "https://api.github.com"
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_ORG_ID: Optional[str] = None
    
    # AI Model configuration
    OPENAI_MODEL_SMALL: str = "gpt-4o-mini"  # For smaller PRs
    OPENAI_MODEL_LARGE: str = "gpt-4o"       # For larger PRs
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_TOKENS: int = 2000
    
    # PR Analysis thresholds
    SMALL_PR_THRESHOLD: int = 100    # Lines changed
    MEDIUM_PR_THRESHOLD: int = 500   # Lines changed
    MAX_COMMENTS_PER_PR: int = 20
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Timeouts (seconds)
    GITHUB_API_TIMEOUT: int = 30
    OPENAI_API_TIMEOUT: int = 120
    WEBHOOK_TIMEOUT: int = 30
    
    # File processing
    MAX_FILE_SIZE_KB: int = 500
    SUPPORTED_FILE_EXTENSIONS: List[str] = [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", 
        ".c", ".cpp", ".h", ".hpp", ".cs", ".php", ".rb", ".swift",
        ".kt", ".scala", ".clj", ".elm", ".dart", ".vue", ".svelte"
    ]
    
    # Default configuration
    DEFAULT_REVIEW_LEVEL: str = "standard"
    DEFAULT_FOCUS_AREAS: List[str] = ["security", "performance", "maintainability"]
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be development, staging, or production")
        return v
    
    @validator("DEBUG", pre=True)
    def debug_from_env(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return v
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load from environment variables
        self.GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
        self.GITHUB_PRIVATE_KEY = os.getenv("GITHUB_PRIVATE_KEY")
        self.GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")
        
        # Set debug mode based on environment
        if self.ENVIRONMENT == "development":
            self.DEBUG = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()