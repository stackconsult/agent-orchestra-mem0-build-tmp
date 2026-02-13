"""
Rate Limiting Middleware

Implements rate limiting for API endpoints to prevent abuse and DoS attacks.
"""

import os
import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """In-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        # Store request timestamps per IP
        self.requests: Dict[str, deque] = defaultdict(deque)
        # Rate limits (requests per minute)
        self.limits = {
            "default": int(os.getenv("RATE_LIMIT_DEFAULT", "60")),  # 60/min
            "invoke": int(os.getenv("RATE_LIMIT_INVOKE", "10")),      # 10/min
            "auth": int(os.getenv("RATE_LIMIT_AUTH", "5")),           # 5/min
            "upload": int(os.getenv("RATE_LIMIT_UPLOAD", "20")),      # 20/min
        }
        # Window size in seconds
        self.window_size = 60
    
    def is_allowed(self, key: str, limit: int) -> bool:
        """Check if request is allowed based on rate limit."""
        now = time.time()
        requests = self.requests[key]
        
        # Remove old requests outside the window
        while requests and requests[0] <= now - self.window_size:
            requests.popleft()
        
        # Check if under limit
        if len(requests) < limit:
            requests.append(now)
            return True
        
        return False
    
    def get_limit_for_endpoint(self, path: str, method: str) -> int:
        """Get rate limit for specific endpoint."""
        path_lower = path.lower()
        
        # Model invocation endpoints (most restrictive)
        if "/invoke" in path_lower or "/chat" in path_lower:
            return self.limits["invoke"]
        
        # Authentication endpoints
        if "/auth" in path_lower or "/login" in path_lower or "/token" in path_lower:
            return self.limits["auth"]
        
        # File upload endpoints
        if "/upload" in path_lower and method.upper() == "POST":
            return self.limits["upload"]
        
        # Default limit
        return self.limits["default"]

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        self.enabled = os.getenv("RATE_LIMITING_ENABLED", "true").lower() == "true"
    
    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting."""
        if not self.enabled:
            return await call_next(request)
        
        # Get client IP (considering proxies)
        client_ip = self._get_client_ip(request)
        
        # Get rate limit for this endpoint
        limit = self.rate_limiter.get_limit_for_endpoint(
            request.url.path, 
            request.method
        )
        
        # Create rate limit key
        key = f"{client_ip}:{request.url.path}:{request.method}"
        
        # Check rate limit
        if not self.rate_limiter.is_allowed(key, limit):
            logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
            
            # Add rate limit headers
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60),
                "Retry-After": "60"
            }
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
                headers=headers
            )
        
        # Add rate limit headers to successful responses
        response = await call_next(request)
        
        remaining_requests = limit - len(self.rate_limiter.requests[key])
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining_requests))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, considering proxies."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fall back to client IP
        return request.client.host if request.client else "unknown"

# Decorator for endpoint-specific rate limiting
def rate_limit(limit: int, window: int = 60):
    """Decorator for endpoint-specific rate limiting."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would need to be integrated with the middleware
            # For now, it's a placeholder for future enhancement
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Rate limit configuration
RATE_LIMIT_CONFIG = {
    "enabled": True,
    "default_limit": 60,  # requests per minute
    "endpoint_limits": {
        "/api/v2/invoke": 10,      # Model invocation
        "/api/v1/sessions": 30,    # Session creation
        "/api/v1/auth/login": 5,   # Authentication
        "/api/v1/upload": 20,      # File uploads
    },
    "whitelist_ips": [],  # IPs to exclude from rate limiting
    "blacklist_ips": [],  # IPs to always block
}
