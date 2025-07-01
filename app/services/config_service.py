"""
Configuration service for repository-specific settings
"""

import yaml
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, validator

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import ConfigurationException
from app.services.github_service import GitHubService


class RepoConfig(BaseModel):
    """Repository configuration model"""
    
    enabled: bool = True
    file_patterns: List[str] = [
        "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.go", "*.rs", 
        "*.java", "*.c", "*.cpp", "*.h", "*.hpp", "*.cs", "*.php"
    ]
    exclude_patterns: List[str] = [
        "node_modules/**", "*.min.js", "__pycache__/**", "dist/**", 
        "build/**", "vendor/**", "*.generated.*", "migrations/**"
    ]
    review_level: str = "standard"  # minimal, standard, strict
    focus_areas: List[str] = ["security", "performance", "maintainability"]
    max_comments_per_pr: int = 20
    skip_draft_prs: bool = True
    ai_model_override: Optional[str] = None
    
    # Advanced settings
    require_security_review: bool = False
    security_review_paths: List[str] = ["**/auth/**", "**/security/**", "**/*auth*"]
    skip_style_paths: List[str] = ["**/migrations/**", "**/generated/**"]
    
    @validator("review_level")
    def validate_review_level(cls, v):
        if v not in ["minimal", "standard", "strict"]:
            raise ValueError("Review level must be minimal, standard, or strict")
        return v
    
    @validator("focus_areas")
    def validate_focus_areas(cls, v):
        valid_areas = ["security", "performance", "maintainability", "style", "testing"]
        for area in v:
            if area not in valid_areas:
                raise ValueError(f"Invalid focus area: {area}")
        return v
    
    @validator("max_comments_per_pr")
    def validate_max_comments(cls, v):
        if v < 1 or v > 50:
            raise ValueError("Max comments per PR must be between 1 and 50")
        return v


class ConfigService(LoggerMixin):
    """Service for managing repository configurations"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.default_config = RepoConfig()
    
    async def get_repo_config(
        self,
        installation_id: int,
        owner: str,
        repo_name: str
    ) -> RepoConfig:
        """Get configuration for a repository"""
        try:
            # Try to load config from repository
            github_client = await self.github_service.get_installation_client(installation_id)
            repository = await self.github_service.get_repository(github_client, owner, repo_name)
            
            config_content = await self.github_service.get_repository_content(
                repository, ".boxedbot.yml"
            )
            
            if config_content:
                config_data = yaml.safe_load(config_content)
                config = RepoConfig(**config_data)
                
                self.log_operation(
                    "Repository config loaded",
                    repo=f"{owner}/{repo_name}",
                    source="repository"
                )
                return config
            
            # Fall back to default configuration
            self.log_operation(
                "Using default config",
                repo=f"{owner}/{repo_name}",
                source="default"
            )
            return self.default_config
            
        except Exception as e:
            self.log_error(
                "Config loading",
                e,
                repo=f"{owner}/{repo_name}"
            )
            # Return default config on error
            return self.default_config
    
    def should_analyze_file(self, filename: str, config: RepoConfig) -> bool:
        """Check if file should be analyzed based on configuration"""
        try:
            import fnmatch
            
            # Check exclude patterns first
            for pattern in config.exclude_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    self.logger.debug(f"File {filename} excluded by pattern {pattern}")
                    return False
            
            # Check include patterns
            for pattern in config.file_patterns:
                if fnmatch.fnmatch(filename, pattern):
                    self.logger.debug(f"File {filename} included by pattern {pattern}")
                    return True
            
            # Check if file extension is supported
            file_ext = f".{filename.split('.')[-1]}" if '.' in filename else ""
            if file_ext in settings.SUPPORTED_FILE_EXTENSIONS:
                self.logger.debug(f"File {filename} included by extension {file_ext}")
                return True
            
            self.logger.debug(f"File {filename} not matched by any pattern")
            return False
            
        except Exception as e:
            self.log_error("File analysis check", e, filename=filename)
            return False
    
    def should_skip_style_review(self, filename: str, config: RepoConfig) -> bool:
        """Check if style review should be skipped for file"""
        try:
            import fnmatch
            
            for pattern in config.skip_style_paths:
                if fnmatch.fnmatch(filename, pattern):
                    return True
            return False
            
        except Exception as e:
            self.log_error("Style skip check", e, filename=filename)
            return False
    
    def requires_security_review(self, filename: str, config: RepoConfig) -> bool:
        """Check if file requires security review"""
        try:
            import fnmatch
            
            if not config.require_security_review:
                return False
            
            for pattern in config.security_review_paths:
                if fnmatch.fnmatch(filename, pattern):
                    return True
            return False
            
        except Exception as e:
            self.log_error("Security review check", e, filename=filename)
            return False
    
    def get_focus_areas_for_file(self, filename: str, config: RepoConfig) -> List[str]:
        """Get focus areas for a specific file"""
        focus_areas = config.focus_areas.copy()
        
        # Remove style if file is in skip_style_paths
        if self.should_skip_style_review(filename, config):
            focus_areas = [area for area in focus_areas if area != "style"]
        
        # Add security if required
        if self.requires_security_review(filename, config):
            if "security" not in focus_areas:
                focus_areas.insert(0, "security")
        
        return focus_areas
    
    def validate_config(self, config_data: Dict[str, Any]) -> RepoConfig:
        """Validate and create configuration from data"""
        try:
            return RepoConfig(**config_data)
        except Exception as e:
            raise ConfigurationException(f"Invalid configuration: {e}")
    
    def get_default_config_yaml(self) -> str:
        """Get default configuration as YAML string"""
        config_dict = self.default_config.dict()
        return yaml.dump(config_dict, default_flow_style=False, sort_keys=True)
    
    def create_example_config(self) -> str:
        """Create an example configuration file"""
        example_config = {
            "version": "1.0",
            "enabled": True,
            "files": {
                "include": [
                    "src/**/*.py",
                    "src/**/*.js",
                    "src/**/*.ts",
                    "*.go",
                    "*.rs"
                ],
                "exclude": [
                    "**/node_modules/**",
                    "**/__pycache__/**",
                    "*.min.js",
                    "**/dist/**",
                    "**/build/**"
                ]
            },
            "review": {
                "level": "standard",
                "focus_areas": [
                    "security",
                    "performance",
                    "maintainability"
                ],
                "max_comments_per_pr": 20,
                "skip_draft_prs": True
            },
            "ai": {
                "model_override": None,
                "temperature": 0.1
            },
            "advanced": {
                "require_security_review": False,
                "security_review_paths": [
                    "**/auth/**",
                    "**/security/**",
                    "**/*auth*"
                ],
                "skip_style_paths": [
                    "**/migrations/**",
                    "**/generated/**"
                ]
            }
        }
        
        return yaml.dump(example_config, default_flow_style=False, sort_keys=False)