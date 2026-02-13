"""
Security Configuration for Agent Orchestra

This module contains security-related configurations and validation functions
to ensure secure operation of the context engineering system.
"""

import os
from typing import List, Dict, Any
from pathlib import Path

# Security settings
SECURITY_CONFIG = {
    # Path traversal protection
    "allowed_repo_base_dir": os.getenv("ALLOWED_REPO_BASE_DIR", "/tmp/repos"),
    "max_repo_path_length": int(os.getenv("MAX_REPO_PATH_LENGTH", "256")),
    
    # Information exposure protection
    "default_to_production_mode": os.getenv("DEFAULT_TO_PRODUCTION_MODE", "true").lower() == "true",
    "sanitize_error_messages": os.getenv("SANITIZE_ERROR_MESSAGES", "true").lower() == "true",
    
    # Sensitive keywords to filter from error messages
    "sensitive_keywords": [
        "password", "passwd", "pwd",
        "secret", "secrets",
        "token", "tokens", "jwt",
        "key", "private_key", "api_key",
        "credential", "credentials",
        "auth", "authorization",
        "session", "cookie",
        "database", "db", "sql",
        "internal", "stack trace",
    ],
    
    # Allowed file extensions for repository analysis
    "allowed_file_extensions": {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".txt", ".dockerfile",
        ".sql", ".sh", ".bash", ".zsh",
    },
    
    # Blocked file patterns (never access these)
    "blocked_file_patterns": [
        ".env", ".env.*",
        "*.key", "*.pem", "*.p12",
        "id_rsa", "id_ed25519",
        ".git/", ".svn/", ".hg/",
        "__pycache__/", "*.pyc",
        "node_modules/", ".npm/",
        ".venv/", "venv/", "env/",
        "*.log", "*.tmp",
    ],
}

def validate_repo_path_security(repo_path: str) -> Dict[str, Any]:
    """
    Validate repository path against security rules.
    
    Returns:
        Dict with 'valid' boolean and 'reason' string if invalid
    """
    if not repo_path:
        return {"valid": False, "reason": "Empty path"}
    
    # Check length
    if len(repo_path) > SECURITY_CONFIG["max_repo_path_length"]:
        return {"valid": False, "reason": "Path too long"}
    
    # Check for path traversal
    normalized = os.path.normpath(repo_path)
    if ".." in normalized or normalized.startswith("/"):
        return {"valid": False, "reason": "Path traversal detected"}
    
    # Check for blocked patterns
    for pattern in SECURITY_CONFIG["blocked_file_patterns"]:
        if pattern in repo_path:
            return {"valid": False, "reason": f"Blocked pattern: {pattern}"}
    
    return {"valid": True, "reason": None}

def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message to remove sensitive information.
    
    Args:
        message: Original error message
        
    Returns:
        Sanitized error message
    """
    if not SECURITY_CONFIG["sanitize_error_messages"]:
        return message
    
    message_lower = message.lower()
    
    # Check for sensitive keywords
    for keyword in SECURITY_CONFIG["sensitive_keywords"]:
        if keyword in message_lower:
            return "Internal server error"
    
    # Remove potential file paths
    if "/" in message or "\\" in message:
        return "Internal server error"
    
    # Remove potential stack traces
    if "traceback" in message_lower or "line " in message_lower:
        return "Internal server error"
    
    return message

def is_safe_file(file_path: str) -> bool:
    """
    Check if a file is safe to access based on security rules.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if safe, False otherwise
    """
    file_name = os.path.basename(file_path)
    
    # Check blocked patterns
    for pattern in SECURITY_CONFIG["blocked_file_patterns"]:
        if pattern.endswith("*"):
            if file_name.startswith(pattern[:-1]):
                return False
        elif pattern in file_path:
            return False
    
    # Check allowed extensions
    file_ext = Path(file_name).suffix.lower()
    if file_ext and file_ext not in SECURITY_CONFIG["allowed_file_extensions"]:
        return False
    
    return True

def get_security_headers() -> Dict[str, str]:
    """
    Get recommended security headers for HTTP responses.
    
    Returns:
        Dictionary of security headers
    """
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
