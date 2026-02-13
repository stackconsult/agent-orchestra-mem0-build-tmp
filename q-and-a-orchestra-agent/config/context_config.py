"""
Context Engineering Configuration

Configuration for 6-Layer Context Engineering system.
"""

from typing import Dict, Any, Optional
import os
from pydantic import BaseModel, Field


class ContextSourceConfig(BaseModel):
    """Configuration for individual context sources."""
    enabled: bool = True
    priority: int = 100
    timeout_ms: int = 5000
    retry_attempts: int = 2
    cache_ttl_seconds: int = 300


class ContextLayerConfig(BaseModel):
    """Configuration for individual context layers."""
    enabled: bool = True
    max_tokens: int = 2000
    required: bool = False
    fallback_enabled: bool = True


class ContextEngineeringConfig(BaseModel):
    """Main configuration for context engineering."""
    
    # Feature flags
    enabled: bool = Field(default_factory=lambda: os.getenv("CONTEXT_ENGINEERING_ENABLED", "true").lower() == "true")
    debug_mode: bool = Field(default_factory=lambda: os.getenv("CONTEXT_DEBUG", "false").lower() == "true")
    
    # Token budget
    max_total_tokens: int = Field(default=8000, env="MAX_CONTEXT_TOKENS")
    token_safety_margin: float = Field(default=0.1, ge=0.0, le=0.5)
    
    # Layer configurations
    layers: Dict[str, ContextLayerConfig] = Field(default_factory=lambda: {
        "user": ContextLayerConfig(max_tokens=2000, required=True),
        "intent": ContextLayerConfig(max_tokens=1000, required=True),
        "domain": ContextLayerConfig(max_tokens=2000, required=False),
        "rules": ContextLayerConfig(max_tokens=1500, required=True),
        "environment": ContextLayerConfig(max_tokens=1000, required=True),
        "exposition": ContextLayerConfig(max_tokens=500, required=True),
    })
    
    # Source configurations
    sources: Dict[str, ContextSourceConfig] = Field(default_factory=lambda: {
        "auth_claims": ContextSourceConfig(priority=100, timeout_ms=100),
        "mem0": ContextSourceConfig(priority=90, timeout_ms=2000, cache_ttl_seconds=600),
        "repo_analyzer": ContextSourceConfig(priority=80, timeout_ms=10000, cache_ttl_seconds=1800),
        "config": ContextSourceConfig(priority=70, timeout_ms=500),
        "env_vars": ContextSourceConfig(priority=60, timeout_ms=100),
        "tenant_policies": ContextSourceConfig(priority=85, timeout_ms=1000, cache_ttl_seconds=300),
    })
    
    # Caching
    cache_enabled: bool = Field(default_factory=lambda: os.getenv("CONTEXT_CACHE_ENABLED", "true").lower() == "true")
    cache_ttl_seconds: int = Field(default=300, env="CONTEXT_CACHE_TTL")
    cache_max_size: int = Field(default=1000, env="CONTEXT_CACHE_MAX_SIZE")
    
    # Performance
    parallel_build: bool = True
    build_timeout_ms: int = Field(default=15000, env="CONTEXT_BUILD_TIMEOUT")
    
    # Compliance
    audit_context_building: bool = Field(default_factory=lambda: os.getenv("CONTEXT_AUDIT_ENABLED", "true").lower() == "true")
    log_context_tokens: bool = Field(default_factory=lambda: os.getenv("CONTEXT_LOG_TOKENS", "false").lower() == "true")
    
    # Routing integration
    influence_model_routing: bool = True
    routing_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Default configuration instance
default_config = ContextEngineeringConfig()


def get_context_config() -> ContextEngineeringConfig:
    """Get the context engineering configuration."""
    return default_config


def update_context_config(updates: Dict[str, Any]) -> None:
    """Update the context configuration."""
    global default_config
    if isinstance(updates, dict):
        # Merge updates into default config
        current_config = default_config.dict()
        deep_merge(current_config, updates)
        default_config = ContextEngineeringConfig(**current_config)


def deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
    """Deep merge updates into base dictionary."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


# Environment-specific presets
def get_production_config() -> ContextEngineeringConfig:
    """Get production-ready context configuration."""
    config = ContextEngineeringConfig(
        debug_mode=False,
        max_total_tokens=6000,  # More conservative in production
        cache_ttl_seconds=600,  # Longer cache in production
        audit_context_building=True,
        log_context_tokens=True,
        parallel_build=True,
        build_timeout_ms=10000,  # Faster timeout in production
    )
    
    # Tighten source timeouts in production
    config.sources["mem0"].timeout_ms = 1500
    config.sources["repo_analyzer"].timeout_ms = 8000
    
    return config


def get_development_config() -> ContextEngineeringConfig:
    """Get development-friendly context configuration."""
    config = ContextEngineeringConfig(
        debug_mode=True,
        max_total_tokens=8000,
        cache_ttl_seconds=60,  # Shorter cache for development
        audit_context_building=False,
        log_context_tokens=True,
        parallel_build=True,
        build_timeout_ms=30000,  # Longer timeout for debugging
    )
    
    # More lenient timeouts in development
    config.sources["mem0"].timeout_ms = 5000
    config.sources["repo_analyzer"].timeout_ms = 20000
    
    return config


# Load environment-specific config
def load_environment_config() -> ContextEngineeringConfig:
    """Load configuration based on current environment."""
    env = os.getenv("ENV", os.getenv("ENVIRONMENT", "development")).lower()
    
    if env == "production":
        return get_production_config()
    elif env == "development":
        return get_development_config()
    else:
        return default_config


# Initialize config with environment-specific settings
default_config = load_environment_config()
