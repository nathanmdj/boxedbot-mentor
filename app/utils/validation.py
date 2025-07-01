"""
Validation utilities for requests and data
"""

import re
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, validator

from app.core.logging import LoggerMixin
from app.core.exceptions import ValidationException


class GitHubValidator(LoggerMixin):
    """Validator for GitHub-related data"""
    
    @staticmethod
    def validate_repo_identifier(repo_id: str) -> tuple[str, str]:
        """Validate and parse repository identifier"""
        if not repo_id or not isinstance(repo_id, str):
            raise ValidationException("Repository ID is required")
        
        if "/" not in repo_id:
            raise ValidationException("Repository ID must be in format 'owner/repo'")
        
        parts = repo_id.split("/")
        if len(parts) != 2:
            raise ValidationException("Repository ID must be in format 'owner/repo'")
        
        owner, repo_name = parts
        
        # Validate owner
        if not GitHubValidator.is_valid_username(owner):
            raise ValidationException(f"Invalid owner name: {owner}")
        
        # Validate repository name
        if not GitHubValidator.is_valid_repo_name(repo_name):
            raise ValidationException(f"Invalid repository name: {repo_name}")
        
        return owner, repo_name
    
    @staticmethod
    def is_valid_username(username: str) -> bool:
        """Validate GitHub username format"""
        if not username or len(username) > 39:
            return False
        
        # GitHub username rules:
        # - Alphanumeric characters or single hyphens
        # - Cannot begin or end with a hyphen
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$'
        return re.match(pattern, username) is not None
    
    @staticmethod
    def is_valid_repo_name(repo_name: str) -> bool:
        """Validate GitHub repository name format"""
        if not repo_name or len(repo_name) > 100:
            return False
        
        # GitHub repository name rules:
        # - Alphanumeric, hyphens, underscores, and periods
        # - Cannot start with period or underscore
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$'
        return re.match(pattern, repo_name) is not None
    
    @staticmethod
    def validate_installation_id(installation_id: Any) -> int:
        """Validate GitHub installation ID"""
        if installation_id is None:
            raise ValidationException("Installation ID is required")
        
        try:
            installation_id = int(installation_id)
            if installation_id <= 0:
                raise ValidationException("Installation ID must be positive")
            return installation_id
        except (ValueError, TypeError):
            raise ValidationException("Installation ID must be a valid integer")
    
    @staticmethod
    def validate_pr_number(pr_number: Any) -> int:
        """Validate pull request number"""
        if pr_number is None:
            raise ValidationException("PR number is required")
        
        try:
            pr_number = int(pr_number)
            if pr_number <= 0:
                raise ValidationException("PR number must be positive")
            return pr_number
        except (ValueError, TypeError):
            raise ValidationException("PR number must be a valid integer")


class ConfigValidator(LoggerMixin):
    """Validator for configuration data"""
    
    @staticmethod
    def validate_review_level(level: str) -> str:
        """Validate review level"""
        valid_levels = ["minimal", "standard", "strict"]
        if level not in valid_levels:
            raise ValidationException(f"Review level must be one of: {valid_levels}")
        return level
    
    @staticmethod
    def validate_focus_areas(areas: List[str]) -> List[str]:
        """Validate focus areas"""
        valid_areas = ["security", "performance", "maintainability", "style", "testing"]
        
        if not areas:
            raise ValidationException("At least one focus area is required")
        
        for area in areas:
            if area not in valid_areas:
                raise ValidationException(f"Invalid focus area: {area}. Valid areas: {valid_areas}")
        
        return list(set(areas))  # Remove duplicates
    
    @staticmethod
    def validate_file_patterns(patterns: List[str]) -> List[str]:
        """Validate file patterns"""
        if not patterns:
            raise ValidationException("At least one file pattern is required")
        
        validated_patterns = []
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValidationException(f"Invalid file pattern: {pattern}")
            
            # Basic pattern validation
            pattern = pattern.strip()
            if len(pattern) > 200:
                raise ValidationException(f"File pattern too long: {pattern}")
            
            validated_patterns.append(pattern)
        
        return validated_patterns
    
    @staticmethod
    def validate_max_comments(max_comments: int) -> int:
        """Validate maximum comments per PR"""
        if not isinstance(max_comments, int):
            raise ValidationException("Max comments must be an integer")
        
        if max_comments < 1 or max_comments > 50:
            raise ValidationException("Max comments must be between 1 and 50")
        
        return max_comments


class WebhookValidator(LoggerMixin):
    """Validator for webhook data"""
    
    @staticmethod
    def validate_webhook_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Validate required webhook headers"""
        required_headers = [
            "x-github-event",
            "x-hub-signature-256"
        ]
        
        # Convert to lowercase for case-insensitive lookup
        header_dict = {k.lower(): v for k, v in headers.items()}
        
        validated_headers = {}
        for header in required_headers:
            if header not in header_dict:
                raise ValidationException(f"Missing required header: {header}")
            validated_headers[header] = header_dict[header]
        
        return validated_headers
    
    @staticmethod
    def validate_webhook_event_type(event_type: str) -> str:
        """Validate webhook event type"""
        if not event_type:
            raise ValidationException("Event type is required")
        
        supported_events = [
            "pull_request",
            "pull_request_review",
            "installation",
            "installation_repositories",
            "ping"
        ]
        
        if event_type not in supported_events:
            # Don't raise error, just log it
            return event_type
        
        return event_type
    
    @staticmethod
    def validate_webhook_payload(payload: Dict[str, Any], event_type: str) -> Dict[str, Any]:
        """Validate webhook payload structure"""
        if not payload:
            raise ValidationException("Payload is required")
        
        # Event-specific validation
        if event_type == "pull_request":
            WebhookValidator._validate_pr_payload(payload)
        elif event_type == "installation":
            WebhookValidator._validate_installation_payload(payload)
        
        return payload
    
    @staticmethod
    def _validate_pr_payload(payload: Dict[str, Any]) -> None:
        """Validate pull request payload"""
        required_fields = [
            "action",
            "pull_request",
            "repository",
            "installation"
        ]
        
        for field in required_fields:
            if field not in payload:
                raise ValidationException(f"Missing required field in PR payload: {field}")
        
        # Validate PR object
        pr = payload["pull_request"]
        pr_required_fields = ["id", "number", "title", "head", "base", "user"]
        
        for field in pr_required_fields:
            if field not in pr:
                raise ValidationException(f"Missing required field in PR object: {field}")
    
    @staticmethod
    def _validate_installation_payload(payload: Dict[str, Any]) -> None:
        """Validate installation payload"""
        required_fields = ["action", "installation"]
        
        for field in required_fields:
            if field not in payload:
                raise ValidationException(f"Missing required field in installation payload: {field}")


class APIValidator(LoggerMixin):
    """General API validation utilities"""
    
    @staticmethod
    def validate_pagination_params(
        page: Optional[int] = None,
        per_page: Optional[int] = None
    ) -> Dict[str, int]:
        """Validate pagination parameters"""
        # Default values
        validated_page = 1
        validated_per_page = 20
        
        if page is not None:
            try:
                validated_page = int(page)
                if validated_page < 1:
                    raise ValidationException("Page number must be positive")
                if validated_page > 1000:
                    raise ValidationException("Page number too large")
            except (ValueError, TypeError):
                raise ValidationException("Page must be a valid integer")
        
        if per_page is not None:
            try:
                validated_per_page = int(per_page)
                if validated_per_page < 1:
                    raise ValidationException("Per page count must be positive")
                if validated_per_page > 100:
                    raise ValidationException("Per page count cannot exceed 100")
            except (ValueError, TypeError):
                raise ValidationException("Per page must be a valid integer")
        
        return {
            "page": validated_page,
            "per_page": validated_per_page
        }
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValidationException("Value must be a string")
        
        # Strip whitespace
        value = value.strip()
        
        # Check length
        if len(value) > max_length:
            raise ValidationException(f"String too long (max {max_length} characters)")
        
        # Basic sanitization (remove null bytes, etc.)
        value = value.replace('\x00', '')
        
        return value
    
    @staticmethod
    def validate_email(email: str) -> str:
        """Validate email format"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            raise ValidationException("Invalid email format")
        
        return email.lower()
    
    @staticmethod
    def validate_url(url: str) -> str:
        """Validate URL format"""
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        
        if not re.match(url_pattern, url):
            raise ValidationException("Invalid URL format")
        
        return url