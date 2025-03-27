from typing import Callable, Optional, Tuple, Type
import time

class RetryError(Exception):
    """Raised when all retry attempts fail."""
    pass

def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Total attempts (including first try).
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay between attempts.
        backoff_factor: Multiplier for delay each retry.
        retryable_exceptions: Exceptions triggering a retry.
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_attempts:
                        raise RetryError(f"All {max_attempts} attempts failed") from e
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            return None
        return wrapper
    return decorator