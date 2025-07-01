"""
Retry utilities for resilient API calls
"""

import asyncio
import random
from typing import Any, Callable, Optional, Dict, Type, Union
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log
)

from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import (
    GitHubAPIException,
    OpenAIAPIException,
    RateLimitException
)

logger = get_logger(__name__)


def retry_on_api_error(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for retrying API calls with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to wait times
    """
    
    def decorator(func):
        wait_strategy = (
            wait_random_exponential(multiplier=1, max=max_wait)
            if jitter
            else wait_exponential(multiplier=min_wait, min=min_wait, max=max_wait)
        )
        
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_strategy,
            retry=retry_if_exception_type((
                GitHubAPIException,
                OpenAIAPIException,
                ConnectionError,
                TimeoutError
            )),
            before_sleep=before_sleep_log(logger, logger.INFO),
            reraise=True
        )
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except RateLimitException:
                # Don't retry on rate limit - let it bubble up
                raise
            except Exception as e:
                logger.warning(f"Retrying {func.__name__} due to error: {e}")
                raise
        
        return wrapper
    
    return decorator


def retry_on_github_error(max_attempts: int = 3):
    """Decorator specifically for GitHub API retries"""
    return retry_on_api_error(
        max_attempts=max_attempts,
        min_wait=2.0,
        max_wait=30.0,
        jitter=True
    )


def retry_on_openai_error(max_attempts: int = 3):
    """Decorator specifically for OpenAI API retries"""
    return retry_on_api_error(
        max_attempts=max_attempts,
        min_wait=1.0,
        max_wait=60.0,
        jitter=True
    )


class RetryableOperation:
    """Class for creating retryable operations with custom logic"""
    
    def __init__(
        self,
        operation: Callable,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple = None
    ):
        self.operation = operation
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        
        if retryable_exceptions is None:
            self.retryable_exceptions = (
                GitHubAPIException,
                OpenAIAPIException,
                ConnectionError,
                TimeoutError
            )
        else:
            self.retryable_exceptions = retryable_exceptions
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the operation with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.max_attempts} for operation")
                result = await self.operation(*args, **kwargs)
                
                if attempt > 0:
                    logger.info(f"Operation succeeded on attempt {attempt + 1}")
                
                return result
                
            except self.retryable_exceptions as e:
                last_exception = e
                
                if attempt == self.max_attempts - 1:
                    # Last attempt, don't wait
                    logger.error(f"Operation failed after {self.max_attempts} attempts: {e}")
                    break
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                
                logger.warning(
                    f"Operation failed on attempt {attempt + 1}, "
                    f"retrying in {delay:.2f}s: {e}"
                )
                
                await asyncio.sleep(delay)
            
            except Exception as e:
                # Non-retryable exception
                logger.error(f"Operation failed with non-retryable error: {e}")
                raise
        
        # All attempts exhausted
        raise last_exception
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the next attempt"""
        # Exponential backoff
        delay = self.base_delay * (self.backoff_factor ** attempt)
        
        # Apply max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)


class CircuitBreaker:
    """Circuit breaker pattern for failing fast on repeated errors"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with circuit breaker protection"""
        
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN - operation not attempted")
        
        try:
            result = await operation(*args, **kwargs)
            
            # Success - reset circuit breaker
            if self.state == 'HALF_OPEN':
                self._reset()
                logger.info("Circuit breaker reset to CLOSED state")
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            
            if self.state == 'HALF_OPEN':
                self.state = 'OPEN'
                logger.warning("Circuit breaker failed in HALF_OPEN, returning to OPEN")
            elif self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                logger.warning(
                    f"Circuit breaker OPENED after {self.failure_count} failures"
                )
            
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        import time
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _record_failure(self) -> None:
        """Record a failure"""
        import time
        self.failure_count += 1
        self.last_failure_time = time.time()
    
    def _reset(self) -> None:
        """Reset circuit breaker to initial state"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'


# Pre-configured retry decorators for common use cases

github_retry = retry_on_github_error(max_attempts=3)
openai_retry = retry_on_openai_error(max_attempts=3)

# Circuit breakers for external services
github_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=120.0,
    expected_exception=GitHubAPIException
)

openai_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0,
    expected_exception=OpenAIAPIException
)


async def with_retry_and_circuit_breaker(
    operation: Callable,
    circuit_breaker: CircuitBreaker,
    max_attempts: int = 3,
    *args,
    **kwargs
) -> Any:
    """
    Execute operation with both retry logic and circuit breaker protection
    """
    retryable_op = RetryableOperation(
        operation=lambda: circuit_breaker.call(operation, *args, **kwargs),
        max_attempts=max_attempts
    )
    
    return await retryable_op.execute()