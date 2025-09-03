"""
Retry tracking utilities for Temporal activities.
Provides decorators and utilities for tracking activity attempts and retries.
"""

import time
import asyncio
import sys
import os
from functools import wraps
from typing import Dict, Any, Optional, Callable

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import startup_db
from db.queries import RetryQueries

def track_activity_attempts(activity_name: str):
    """Decorator to track activity attempts and retries."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract order_id from arguments (assume first arg contains it)
            order_id = None
            attempt_number = 1
            
            try:
                # Try to extract order_id from first argument
                if args and isinstance(args[0], dict):
                    order_data = args[0]
                    order_id = order_data.get("order_id")
                    attempt_number = order_data.get("attempt_number", 1)
                
                if not order_id:
                    # Fallback: try to extract from kwargs or use a default
                    order_id = kwargs.get("order_id", "UNKNOWN")
                
                # Initialize database
                await startup_db()
                
                # Log attempt start
                start_time = time.time()
                await RetryQueries.log_activity_attempt(
                    order_id=order_id,
                    activity_name=activity_name,
                    attempt_number=attempt_number,
                    status="started",
                    input_data={"args": args, "kwargs": kwargs} if args or kwargs else None
                )
                
                try:
                    # Execute the actual activity
                    result = await func(*args, **kwargs)
                    
                    # Log successful completion
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    await RetryQueries.log_activity_attempt(
                        order_id=order_id,
                        activity_name=activity_name,
                        attempt_number=attempt_number,
                        status="completed",
                        output_data=result if isinstance(result, dict) else {"result": str(result)},
                        execution_time_ms=execution_time_ms
                    )
                    
                    return result
                    
                except asyncio.TimeoutError as e:
                    # Log timeout
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    await RetryQueries.log_activity_attempt(
                        order_id=order_id,
                        activity_name=activity_name,
                        attempt_number=attempt_number,
                        status="timeout",
                        error_message=str(e),
                        execution_time_ms=execution_time_ms
                    )
                    raise
                    
                except Exception as e:
                    # Log failure
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    await RetryQueries.log_activity_attempt(
                        order_id=order_id,
                        activity_name=activity_name,
                        attempt_number=attempt_number,
                        status="failed",
                        error_message=str(e),
                        execution_time_ms=execution_time_ms
                    )
                    raise
                    
            except Exception as e:
                # If even logging fails, just continue with the original error
                print(f"⚠️  Failed to track attempt for {activity_name}: {e}")
                # Still execute the original function
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

async def log_retry_event(order_id: str, activity_name: str, attempt_number: int, reason: str):
    """Log a retry event for observability."""
    try:
        from db.queries import EventQueries
        await EventQueries.log_event(order_id, f"{activity_name}_retry", {
            "attempt_number": attempt_number,
            "retry_reason": reason,
            "source": "retry_tracker"
        })
    except Exception as e:
        print(f"⚠️  Failed to log retry event: {e}")

async def get_activity_attempt_count(order_id: str, activity_name: str) -> int:
    """Get the current attempt count for an activity."""
    try:
        attempts = await RetryQueries.get_order_attempts(order_id)
        activity_attempts = [a for a in attempts if a['activity_name'] == activity_name]
        return len(activity_attempts) + 1  # Next attempt number
    except:
        return 1  # Default to first attempt

class RetryContext:
    """Context manager for tracking retries with enhanced observability."""
    
    def __init__(self, order_id: str, activity_name: str):
        self.order_id = order_id
        self.activity_name = activity_name
        self.attempt_number = 1
        self.start_time = None
    
    async def __aenter__(self):
        """Enter retry context."""
        try:
            await startup_db()
            self.attempt_number = await get_activity_attempt_count(self.order_id, self.activity_name)
            self.start_time = time.time()
            
            await RetryQueries.log_activity_attempt(
                order_id=self.order_id,
                activity_name=self.activity_name,
                attempt_number=self.attempt_number,
                status="started"
            )
        except Exception as e:
            print(f"⚠️  Failed to initialize retry context: {e}")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit retry context with result logging."""
        try:
            execution_time_ms = int((time.time() - self.start_time) * 1000) if self.start_time else None
            
            if exc_type is None:
                # Success
                await RetryQueries.log_activity_attempt(
                    order_id=self.order_id,
                    activity_name=self.activity_name,
                    attempt_number=self.attempt_number,
                    status="completed",
                    execution_time_ms=execution_time_ms
                )
            elif issubclass(exc_type, asyncio.TimeoutError):
                # Timeout
                await RetryQueries.log_activity_attempt(
                    order_id=self.order_id,
                    activity_name=self.activity_name,
                    attempt_number=self.attempt_number,
                    status="timeout",
                    error_message=str(exc_val),
                    execution_time_ms=execution_time_ms
                )
            else:
                # Failure
                await RetryQueries.log_activity_attempt(
                    order_id=self.order_id,
                    activity_name=self.activity_name,
                    attempt_number=self.attempt_number,
                    status="failed",
                    error_message=str(exc_val),
                    execution_time_ms=execution_time_ms
                )
        except Exception as e:
            print(f"⚠️  Failed to log retry context exit: {e}")
        
        return False  # Don't suppress exceptions