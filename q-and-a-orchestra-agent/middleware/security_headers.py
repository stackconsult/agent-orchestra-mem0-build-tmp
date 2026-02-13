"""
Security Headers Middleware

Adds comprehensive security headers to all HTTP responses.
"""

import os
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    def __init__(self, app):
        super().__init__(app)
        self.env = os.getenv("ENV", "development")
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Content Security Policy (prevent XSS)
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "img-src 'self' data: https:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self' https:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "media-src 'self'",
            "manifest-src 'self'"
        ]
        
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # HSTS (enforce HTTPS) - only in production
        if self.env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (restrict browser features)
        permissions_policy = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
            "ambient-light-sensor=()",
            "autoplay=()",
            "encrypted-media=()",
            "fullscreen=()",
            "picture-in-picture=()"
        ]
        
        response.headers["Permissions-Policy"] = ", ".join(permissions_policy)
        
        # Additional security headers
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        
        # Cache control for sensitive endpoints
        if self._is_sensitive_endpoint(request.url.path):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response
    
    def _is_sensitive_endpoint(self, path: str) -> bool:
        """Check if endpoint is sensitive and shouldn't be cached."""
        sensitive_patterns = [
            "/api/v1/auth",
            "/api/v2/invoke",
            "/api/v1/sessions",
            "/admin",
            "/health",
            "/metrics"
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for consistent error handling and sanitization."""
    
    def __init__(self, app):
        super().__init__(app)
        self.env = os.getenv("ENV", "development")
    
    async def dispatch(self, request: Request, call_next):
        """Handle exceptions and sanitize error messages."""
        try:
            return await call_next(request)
        except Exception as exc:
            # Log full error internally
            logger.error(
                f"Unhandled exception: {str(exc)}",
                exc_info=True,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": self._get_client_ip(request)
                }
            )
            
            # Return sanitized error to client
            # Default to production mode for security
            is_production = self.env == "production" or self.env is None
            
            if is_production:
                # Production: hide all details
                error_response = {
                    "error": "Internal server error",
                    "request_id": request.headers.get("x-request-id", "unknown"),
                    "timestamp": self._get_timestamp()
                }
            else:
                # Development: show limited details (no stack traces)
                error_response = {
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "path": request.url.path,
                    "method": request.method,
                    "timestamp": self._get_timestamp()
                }
                
                # Remove any potential sensitive information from error message
                if "password" in str(exc).lower() or "secret" in str(exc).lower() or "token" in str(exc).lower():
                    error_response["error"] = "Internal server error"
            
            return JSONResponse(
                status_code=500,
                content=error_response,
                headers={
                    "X-Error-Handled": "true",
                    "X-Request-ID": request.headers.get("x-request-id", "unknown")
                }
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        return request.client.host if request.client else "unknown"
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

# Validation middleware for request size limits
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request sizes."""
    
    def __init__(self, app, max_size_mb: int = 10):
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing."""
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_size_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "max_size_mb": self.max_size_bytes // (1024 * 1024),
                    "received_mb": int(content_length) // (1024 * 1024)
                }
            )
        
        return await call_next(request)
