"""
CORS Security Configuration

Environment-based CORS configuration to prevent wildcard origins.
"""

import os
from typing import List

def get_allowed_origins() -> List[str]:
    """Get CORS allowed origins from environment."""
    env = os.getenv("ENV", "development")
    
    if env == "production":
        # Production: specific domains only
        allowed = [
            os.getenv("APP_URL", "https://api.yourdomain.com"),
            os.getenv("FRONTEND_URL", "https://yourdomain.com")
        ]
        # Remove any empty values and placeholder URLs
        return [url for url in allowed if url and url != "https://api.yourdomain.com" and url != "https://yourdomain.com"]
    
    elif env == "staging":
        return [
            "https://staging-api.yourdomain.com",
            "https://staging.yourdomain.com",
            "http://localhost:3000",
            "http://localhost:8000"
        ]
    
    else:  # development
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000"
        ]

def get_allowed_methods() -> List[str]:
    """Get allowed HTTP methods."""
    return ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

def get_allowed_headers() -> List[str]:
    """Get allowed headers."""
    return [
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin"
    ]

def get_cors_config() -> dict:
    """Get complete CORS configuration."""
    return {
        "allow_origins": get_allowed_origins(),
        "allow_credentials": True,
        "allow_methods": get_allowed_methods(),
        "allow_headers": get_allowed_headers(),
        "max_age": 3600  # Cache preflight for 1 hour
    }
