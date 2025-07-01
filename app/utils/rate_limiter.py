"""
Rate limiting utilities
"""

import time
from typing import Dict, Optional, Any
from collections import defaultdict, deque

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import RateLimitException


class RateLimiter(LoggerMixin):
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        # Store request timestamps for each key
        self._requests: Dict[str, deque] = defaultdict(deque)
        # Store rate limit configurations
        self._limits: Dict[str, Dict[str, int]] = {}
        
        # Default limits
        self._default_limits = {
            'requests_per_minute': settings.RATE_LIMIT_PER_MINUTE,
            'requests_per_hour': settings.RATE_LIMIT_PER_HOUR
        }
    
    def check_rate_limit(
        self,
        key: str,
        limits: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """Check if request is within rate limits"""
        
        current_time = time.time()
        limits = limits or self._default_limits
        
        # Clean old requests
        self._cleanup_old_requests(key, current_time)
        
        # Check each limit
        for limit_name, max_requests in limits.items():
            window_seconds = self._get_window_seconds(limit_name)
            if window_seconds is None:
                continue
            
            # Count requests in the current window
            window_start = current_time - window_seconds
            recent_requests = sum(
                1 for req_time in self._requests[key]
                if req_time >= window_start
            )
            
            if recent_requests >= max_requests:
                # Rate limit exceeded
                retry_after = self._calculate_retry_after(key, limit_name, current_time)
                
                self.log_error(
                    "Rate limit exceeded",
                    RateLimitException("Rate limit exceeded"),
                    key=key,
                    limit=limit_name,
                    requests=recent_requests,
                    max_requests=max_requests
                )
                
                raise RateLimitException(
                    f"Rate limit exceeded for {limit_name}",
                    retry_after=retry_after
                )
        
        # Record this request
        self._requests[key].append(current_time)
        
        # Calculate remaining requests
        remaining = self._calculate_remaining(key, limits, current_time)
        
        return {
            'allowed': True,
            'remaining': remaining,
            'reset_time': current_time + 60  # Next minute reset
        }
    
    def _get_window_seconds(self, limit_name: str) -> Optional[int]:
        """Get window size in seconds for limit type"""
        window_map = {
            'requests_per_minute': 60,
            'requests_per_hour': 3600,
            'requests_per_day': 86400
        }
        return window_map.get(limit_name)
    
    def _cleanup_old_requests(self, key: str, current_time: float) -> None:
        """Remove requests older than the largest window"""
        if key not in self._requests:
            return
        
        # Keep requests from the last hour (largest common window)
        cutoff_time = current_time - 3600
        
        while self._requests[key] and self._requests[key][0] < cutoff_time:
            self._requests[key].popleft()
    
    def _calculate_retry_after(self, key: str, limit_name: str, current_time: float) -> int:
        """Calculate when the client can retry"""
        window_seconds = self._get_window_seconds(limit_name)
        if window_seconds is None:
            return 60  # Default retry after 1 minute
        
        if key not in self._requests or not self._requests[key]:
            return 1
        
        # Find the oldest request in the current window
        window_start = current_time - window_seconds
        oldest_in_window = None
        
        for req_time in self._requests[key]:
            if req_time >= window_start:
                oldest_in_window = req_time
                break
        
        if oldest_in_window is None:
            return 1
        
        # Retry after the oldest request in window expires
        retry_after = int(oldest_in_window + window_seconds - current_time) + 1
        return max(1, retry_after)
    
    def _calculate_remaining(
        self,
        key: str,
        limits: Dict[str, int],
        current_time: float
    ) -> Dict[str, int]:
        """Calculate remaining requests for each limit"""
        remaining = {}
        
        for limit_name, max_requests in limits.items():
            window_seconds = self._get_window_seconds(limit_name)
            if window_seconds is None:
                continue
            
            window_start = current_time - window_seconds
            recent_requests = sum(
                1 for req_time in self._requests[key]
                if req_time >= window_start
            )
            
            remaining[limit_name] = max(0, max_requests - recent_requests)
        
        return remaining
    
    def get_rate_limit_status(self, key: str) -> Dict[str, Any]:
        """Get current rate limit status for a key"""
        current_time = time.time()
        self._cleanup_old_requests(key, current_time)
        
        status = {
            'key': key,
            'current_time': current_time,
            'limits': {}
        }
        
        for limit_name, max_requests in self._default_limits.items():
            window_seconds = self._get_window_seconds(limit_name)
            if window_seconds is None:
                continue
            
            window_start = current_time - window_seconds
            recent_requests = sum(
                1 for req_time in self._requests[key]
                if req_time >= window_start
            )
            
            status['limits'][limit_name] = {
                'max_requests': max_requests,
                'current_requests': recent_requests,
                'remaining': max(0, max_requests - recent_requests),
                'window_seconds': window_seconds,
                'reset_time': current_time + window_seconds
            }
        
        return status
    
    def reset_limits(self, key: str) -> None:
        """Reset rate limits for a specific key"""
        if key in self._requests:
            self._requests[key].clear()
        
        self.logger.info(f"Rate limits reset for key: {key}")


class GitHubRateLimiter(RateLimiter):
    """Rate limiter specific to GitHub API limits"""
    
    def __init__(self):
        super().__init__()
        
        # GitHub API specific limits
        self._github_limits = {
            'api_requests_per_hour': 5000,  # GitHub App installations
            'search_requests_per_minute': 30,
            'graphql_requests_per_hour': 5000
        }
    
    def check_github_api_limit(self, installation_id: int, api_type: str = 'api') -> Dict[str, Any]:
        """Check GitHub API rate limits"""
        key = f"github_{api_type}_{installation_id}"
        
        if api_type == 'api':
            limits = {'requests_per_hour': self._github_limits['api_requests_per_hour']}
        elif api_type == 'search':
            limits = {'requests_per_minute': self._github_limits['search_requests_per_minute']}
        elif api_type == 'graphql':
            limits = {'requests_per_hour': self._github_limits['graphql_requests_per_hour']}
        else:
            limits = self._default_limits
        
        return self.check_rate_limit(key, limits)


class OpenAIRateLimiter(RateLimiter):
    """Rate limiter specific to OpenAI API limits"""
    
    def __init__(self):
        super().__init__()
        
        # OpenAI API limits (conservative estimates)
        self._openai_limits = {
            'gpt4_requests_per_minute': 20,
            'gpt4_mini_requests_per_minute': 100,
            'tokens_per_minute': 10000
        }
    
    def check_openai_limit(self, model: str, request_type: str = 'completion') -> Dict[str, Any]:
        """Check OpenAI API rate limits"""
        key = f"openai_{model}_{request_type}"
        
        if 'gpt-4o-mini' in model:
            limits = {'requests_per_minute': self._openai_limits['gpt4_mini_requests_per_minute']}
        elif 'gpt-4' in model:
            limits = {'requests_per_minute': self._openai_limits['gpt4_requests_per_minute']}
        else:
            limits = {'requests_per_minute': 60}  # Conservative default
        
        return self.check_rate_limit(key, limits)


# Global rate limiter instances
rate_limiter = RateLimiter()
github_rate_limiter = GitHubRateLimiter()
openai_rate_limiter = OpenAIRateLimiter()