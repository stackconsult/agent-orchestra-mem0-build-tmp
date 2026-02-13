"""
Context Engineering Module - 6-Layer Framework

StackConsulting Production Pattern: Context Engineering for AI Systems

This module implements the 6-Layer Context Framework:
- User: Who is talking, preferences, history
- Intent: What job they're hiring the system to do
- Domain: Workspace entities and relationships
- Rules: Hard and soft constraints
- Environment: System state and deployment context
- Exposition: Fused, prioritized payload for LLMs

Usage:
    from context_engineering import build_context_envelope, ContextConfig
    
    # Build context from request
    envelope = await build_context_envelope(
        auth_claims=auth_data,
        request_body=request_data,
        mem0_client=mem0,
        repo_analyzer_client=repo_analyzer,
        config=ContextConfig()
    )
    
    # Use in orchestrator
    system_context = envelope.exposition.narrative
    structured_data = envelope.exposition.structured
"""

from .models import (
    UserContext,
    IntentContext,
    DomainContext,
    RulesContext,
    EnvironmentContext,
    ExpositionContext,
    ContextEnvelope,
    ContextConfig,
    ContextOverride,
)

from .builder import (
    build_context_envelope,
    build_exposition,
    apply_token_budget,
)

__version__ = "1.0.0"
__all__ = [
    # Models
    "UserContext",
    "IntentContext",
    "DomainContext",
    "RulesContext",
    "EnvironmentContext",
    "ExpositionContext",
    "ContextEnvelope",
    "ContextConfig",
    "ContextOverride",
    # Builders
    "build_context_envelope",
    "build_exposition",
    "apply_token_budget",
]
