"""
Environment Context Source - Builds Environment Layer

StackConsulting Pattern: Capture current system state, deployment context,
and runtime configuration for context-aware decision making.
"""

import os
import psutil
from typing import Dict, Any, Optional
from datetime import datetime

from ..models import EnvironmentContext

logger = __import__("logging").getLogger(__name__)


def build_environment_context() -> EnvironmentContext:
    """
    Build the Environment layer from system state and configuration.
    
    Returns:
        EnvironmentContext with current environment information
    """
    # Get environment variables with defaults
    environment = os.getenv("ENV", os.getenv("ENVIRONMENT", "development"))
    model_routing_mode = os.getenv("MODEL_ROUTING_MODE", "local-preferred")
    deployment_version = os.getenv("DEPLOYMENT_VERSION", "unknown")
    
    # Parse feature flags
    feature_flags = {
        "semantic_cache": _parse_bool(os.getenv("FEATURE_SEMANTIC_CACHE", "true")),
        "context_engineering_v2": _parse_bool(os.getenv("FEATURE_CONTEXT_ENGINEERING_V2", "true")),
        "audit_logging": _parse_bool(os.getenv("FEATURE_AUDIT_LOGGING", "true")),
        "multi_tenancy": _parse_bool(os.getenv("FEATURE_MULTI_TENANCY", "false")),
        "rate_limiting": _parse_bool(os.getenv("FEATURE_RATE_LIMITING", "true")),
        "advanced_analytics": _parse_bool(os.getenv("FEATURE_ADVANCED_ANALYTICS", "false")),
        "auto_scaling": _parse_bool(os.getenv("FEATURE_AUTO_SCALING", "false")),
        "debug_mode": _parse_bool(os.getenv("DEBUG", "false")),
    }
    
    # Get rate limits from environment
    rate_limits = {
        "chat_per_minute": int(os.getenv("RATE_LIMIT_CHAT_PER_MINUTE", "10")),
        "analytics_per_minute": int(os.getenv("RATE_LIMIT_ANALYTICS_PER_MINUTE", "5")),
        "repo_analysis_per_hour": int(os.getenv("RATE_LIMIT_REPO_ANALYSIS_PER_HOUR", "20")),
        "max_concurrent_sessions": int(os.getenv("MAX_CONCURRENT_SESSIONS", "100")),
    }
    
    # Get system metrics
    system_load = _get_system_load()
    active_sessions = _get_active_sessions_count()
    
    return EnvironmentContext(
        environment=environment,
        model_routing_mode=model_routing_mode,
        feature_flags=feature_flags,
        rate_limits=rate_limits,
        active_sessions=active_sessions,
        system_load=system_load,
        deployment_version=deployment_version,
    )


def _parse_bool(value: str) -> bool:
    """Parse boolean from string."""
    return value.lower() in ("true", "1", "yes", "on", "enabled")


def _get_system_load() -> Optional[float]:
    """Get current system load (0-1 scale)."""
    try:
        # CPU load percentage
        cpu_percent = psutil.cpu_percent(interval=1) / 100
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent / 100
        
        # Return the higher of CPU or memory load
        return max(cpu_percent, memory_percent)
    except Exception as e:
        logger.warning(f"Failed to get system load: {e}")
        return None


def _get_active_sessions_count() -> int:
    """
    Get count of active sessions.
    
    In production, this would query Redis, database, or session store.
    """
    # Mock implementation - in production, query actual session store
    return 42


def get_model_routing_config(environment_context: EnvironmentContext) -> Dict[str, Any]:
    """
    Get model routing configuration based on environment.
    
    Args:
        environment_context: Current environment context
    
    Returns:
        Model routing configuration
    """
    config = {
        "mode": environment_context.model_routing_mode,
        "providers": ["anthropic", "openai", "ollama"],
        "fallback_enabled": True,
        "load_balancing": "round_robin",
    }
    
    # Adjust based on environment
    if environment_context.environment == "production":
        config.update({
            "timeout_seconds": 30,
            "retry_attempts": 3,
            "circuit_breaker_enabled": True,
        })
    elif environment_context.environment == "development":
        config.update({
            "timeout_seconds": 60,
            "retry_attempts": 1,
            "circuit_breaker_enabled": False,
        })
    
    # Adjust based on system load
    if environment_context.system_load and environment_context.system_load > 0.8:
        config["prefer_local_models"] = True
        config["reduce_concurrent_requests"] = True
    
    return config


def should_enable_feature(
    feature_name: str,
    environment_context: EnvironmentContext,
    user_context: Optional[Any] = None
) -> bool:
    """
    Determine if a feature should be enabled based on environment and user context.
    
    Args:
        feature_name: Name of the feature
        environment_context: Current environment context
        user_context: Optional user context for beta features
    
    Returns:
        Whether the feature should be enabled
    """
    # Check if feature is globally enabled
    if not environment_context.feature_flags.get(feature_name, False):
        return False
    
    # Environment-specific rules
    if environment_context.environment == "production":
        # Some features are restricted in production
        restricted_features = ["debug_mode", "experimental_models"]
        if feature_name in restricted_features:
            return False
    
    # User-specific beta features
    if user_context and feature_name.startswith("beta_"):
        # Only enable beta features for specific users
        beta_users = ["admin@stackconsulting.com", "beta_testers@stackconsulting.com"]
        if user_context.user_id not in beta_users:
            return False
    
    # Load shedding for high load
    if environment_context.system_load and environment_context.system_load > 0.9:
        # Disable non-essential features under high load
        non_essential_features = ["advanced_analytics", "auto_scaling"]
        if feature_name in non_essential_features:
            return False
    
    return True


def get_environment_constraints(environment_context: EnvironmentContext) -> Dict[str, Any]:
    """
    Get operational constraints based on environment.
    
    Args:
        environment_context: Current environment context
    
    Returns:
        Dictionary of operational constraints
    """
    constraints = {
        "max_response_time_ms": 30000,
        "max_concurrent_requests": 10,
        "enable_caching": True,
        "log_level": "INFO",
    }
    
    # Adjust based on environment
    if environment_context.environment == "production":
        constraints.update({
            "max_response_time_ms": 10000,
            "max_concurrent_requests": 50,
            "enable_caching": True,
            "log_level": "WARNING",
        })
    elif environment_context.environment == "development":
        constraints.update({
            "max_response_time_ms": 60000,
            "max_concurrent_requests": 5,
            "enable_caching": False,
            "log_level": "DEBUG",
        })
    
    # Adjust based on system load
    if environment_context.system_load:
        if environment_context.system_load > 0.8:
            constraints["max_response_time_ms"] = constraints["max_response_time_ms"] // 2
            constraints["max_concurrent_requests"] = max(1, constraints["max_concurrent_requests"] // 2)
    
    return constraints
