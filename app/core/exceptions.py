"""
Custom exceptions for BoxedBot
"""

from typing import Any, Dict, Optional


class BoxedBotException(Exception):
    """Base exception for BoxedBot"""
    
    def __init__(
        self, 
        message: str, 
        code: str = "BOXEDBOT_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class GitHubAPIException(BoxedBotException):
    """Exception for GitHub API errors"""
    
    def __init__(self, message: str, status_code: Optional[int] = None, **kwargs):
        super().__init__(message, code="GITHUB_API_ERROR", **kwargs)
        self.status_code = status_code


class OpenAIAPIException(BoxedBotException):
    """Exception for OpenAI API errors"""
    
    def __init__(self, message: str, model: Optional[str] = None, **kwargs):
        super().__init__(message, code="OPENAI_API_ERROR", **kwargs)
        self.model = model


class WebhookException(BoxedBotException):
    """Exception for webhook processing errors"""
    
    def __init__(self, message: str, event_type: Optional[str] = None, **kwargs):
        super().__init__(message, code="WEBHOOK_ERROR", **kwargs)
        self.event_type = event_type


class ConfigurationException(BoxedBotException):
    """Exception for configuration errors"""
    
    def __init__(self, message: str, config_field: Optional[str] = None, **kwargs):
        super().__init__(message, code="CONFIGURATION_ERROR", **kwargs)
        self.config_field = config_field


class AuthenticationException(BoxedBotException):
    """Exception for authentication errors"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, code="AUTHENTICATION_ERROR", **kwargs)


class RateLimitException(BoxedBotException):
    """Exception for rate limiting errors"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", **kwargs)
        self.retry_after = retry_after


class PRAnalysisException(BoxedBotException):
    """Exception for PR analysis errors"""
    
    def __init__(self, message: str, pr_number: Optional[int] = None, **kwargs):
        super().__init__(message, code="PR_ANALYSIS_ERROR", **kwargs)
        self.pr_number = pr_number


class FileProcessingException(BoxedBotException):
    """Exception for file processing errors"""
    
    def __init__(self, message: str, filename: Optional[str] = None, **kwargs):
        super().__init__(message, code="FILE_PROCESSING_ERROR", **kwargs)
        self.filename = filename


class ValidationException(BoxedBotException):
    """Exception for validation errors"""
    
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, code="VALIDATION_ERROR", **kwargs)
        self.field = field