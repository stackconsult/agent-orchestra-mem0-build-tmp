"""
Context Builder - Main factory for 6-Layer Context Engineering

StackConsulting Production Pattern: Assembles context from all sources
into a unified ContextEnvelope ready for LLM consumption.
"""

import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from .models import (
    ContextEnvelope,
    ContextConfig,
    ContextOverride,
    ExpositionContext,
    UserContext,
    IntentContext,
    DomainContext,
    RulesContext,
    EnvironmentContext,
)

# Import source builders
from .sources.user_profile import build_user_context
from .sources.intent_detection import detect_intent
from .sources.domain_graph import build_domain_context
from .sources.rules import build_rules_context
from .sources.environment import build_environment_context

logger = __import__("logging").getLogger(__name__)


def build_exposition(
    user: UserContext,
    intent: IntentContext,
    domain: DomainContext,
    rules: RulesContext,
    environment: EnvironmentContext,
    config: ContextConfig,
) -> ExpositionContext:
    """
    Build the Exposition layer - fused, prioritized, token-optimized payload.
    This is where the 6 layers are synthesized into the final context package.
    """
    # Build narrative - human-readable context
    narrative_parts = []
    
    if config.enable_layer.get("user", True) and user.user_id:
        narrative_parts.append(
            f"User:\n"
            f"- ID: {user.user_id}, Tenant: {user.tenant_id}, Roles: {user.roles}\n"
            f"- Expertise: {user.expertise_level or 'unknown'}\n"
            f"- Preferences: {user.preferences}\n"
            f"- History: {user.history_summary or 'No history'}"
        )
    
    if config.enable_layer.get("intent", True):
        narrative_parts.append(
            f"Intent:\n"
            f"- Primary: {intent.primary_intent}\n"
            f"- Task: {intent.task_type or 'Not specified'}\n"
            f"- Success: {intent.success_criteria or 'Deliver actionable response'}\n"
            f"- Constraints: {intent.constraints}"
        )
    
    if config.enable_layer.get("domain", True) and domain.repo_path:
        narrative_parts.append(
            f"Domain:\n"
            f"- Repo: {domain.repo_path}\n"
            f"- Summary: {domain.repo_summary or 'No analysis'}\n"
            f"- Components: {domain.key_components}\n"
            f"- Docs: {list(domain.related_docs.keys())}"
        )
    
    if config.enable_layer.get("rules", True):
        narrative_parts.append(
            f"Rules:\n"
            f"- Soft walls (style): {rules.soft_walls}\n"
            f"- Hard walls (mandatory): {rules.hard_walls}"
        )
    
    if config.enable_layer.get("environment", True):
        narrative_parts.append(
            f"Environment:\n"
            f"- Mode: {environment.environment}\n"
            f"- Routing: {environment.model_routing_mode}\n"
            f"- Features: {environment.feature_flags}\n"
            f"- Load: {environment.system_load or 'unknown'}"
        )
    
    narrative = "\n\n".join(narrative_parts)
    
    # Build structured data - machine-usable pieces
    structured = {
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "roles": user.roles,
        "primary_intent": intent.primary_intent,
        "task_type": intent.task_type,
        "repo_path": domain.repo_path,
        "environment": environment.environment,
        "model_routing": environment.model_routing_mode,
        "hard_walls": rules.hard_walls,
        "feature_flags": environment.feature_flags,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Calculate approximate token count (rough estimate: 4 chars = 1 token)
    token_count = len(narrative) // 4 + len(str(structured)) // 4
    
    # Calculate priority based on intent urgency and system load
    priority_score = 0.5  # Base priority
    if intent.primary_intent in ["architecture_design", "security_analysis"]:
        priority_score += 0.3
    if environment.system_load and environment.system_load > 0.8:
        priority_score += 0.2
    
    return ExpositionContext(
        narrative=narrative.strip(),
        structured=structured,
        token_count=token_count,
        priority_score=priority_score,
        created_at=datetime.utcnow(),
    )


async def build_context_envelope(
    auth_claims: Dict[str, Any],
    request_body: Dict[str, Any],
    mem0_client=None,
    repo_analyzer_client=None,
    tenant_policies: Optional[Dict[str, Any]] = None,
    config: Optional[ContextConfig] = None,
    override: Optional[ContextOverride] = None,
) -> ContextEnvelope:
    """
    Build a complete ContextEnvelope from all available sources.
    
    This is the main entry point for context engineering in the system.
    """
    start_time = time.time()
    context_id = str(uuid.uuid4())
    
    # Use default config if none provided
    if config is None:
        config = ContextConfig()
    
    if override is None:
        override = ContextOverride()
    
    try:
        # Build each layer
        logger.info(f"Building context envelope {context_id}")
        
        # User Layer
        user = build_user_context(auth_claims, mem0_client)
        if override.override_user_preferences:
            user.preferences.update(override.override_user_preferences)
        
        # Intent Layer
        intent = detect_intent(
            request_body.get("message", ""),
            request_body.get("task_type"),
            request_body.get("session_id")
        )
        if override.override_intent:
            for key, value in override.override_intent.items():
                setattr(intent, key, value)
        
        # Domain Layer
        domain = build_domain_context(
            request_body.get("context", {}),
            repo_analyzer_client
        )
        if override.override_domain:
            if "repo_path" in override.override_domain:
                domain.repo_path = override.override_domain["repo_path"]
            if "key_components" in override.override_domain:
                domain.key_components.update(override.override_domain["key_components"])
        
        # Rules Layer
        rules = build_rules_context(tenant_policies)
        if override.override_rules:
            if "soft_walls" in override.override_rules:
                rules.soft_walls.update(override.override_rules["soft_walls"])
            if "hard_walls" in override.override_rules:
                rules.hard_walls.update(override.override_rules["hard_walls"])
        
        # Environment Layer
        environment = build_environment_context()
        if override.override_environment:
            for key, value in override.override_environment.items():
                if hasattr(environment, key):
                    setattr(environment, key, value)
        
        # Exposition Layer - synthesize everything
        exposition = build_exposition(user, intent, domain, rules, environment, config)
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        token_budget_used = exposition.token_count
        
        logger.info(
            f"Context envelope {context_id} built in {processing_time_ms:.2f}ms "
            f"with {token_budget_used} tokens"
        )
        
        return ContextEnvelope(
            context_id=context_id,
            user=user,
            intent=intent,
            domain=domain,
            rules=rules,
            environment=environment,
            exposition=exposition,
            created_at=datetime.utcnow(),
            token_budget_used=token_budget_used,
            processing_time_ms=processing_time_ms,
        )
        
    except Exception as e:
        logger.error(f"Failed to build context envelope {context_id}: {e}")
        # Return minimal context on error
        return ContextEnvelope(
            context_id=context_id,
            user=UserContext(),
            intent=IntentContext(primary_intent="error_recovery"),
            domain=DomainContext(),
            rules=RulesContext(),
            environment=EnvironmentContext(),
            exposition=ExpositionContext(
                narrative="Context building failed, using minimal context",
                structured={"error": str(e)}
            ),
            created_at=datetime.utcnow(),
            token_budget_used=100,
            processing_time_ms=(time.time() - start_time) * 1000,
        )


def apply_token_budget(envelope: ContextEnvelope, max_tokens: int = 8000) -> ContextEnvelope:
    """
    Apply token budget constraints by pruning less critical content.
    """
    if envelope.token_budget_used <= max_tokens:
        return envelope
    
    # Calculate reduction factor
    reduction_factor = max_tokens / envelope.token_budget_used
    
    # Prune narrative content
    narrative = envelope.exposition.narrative
    target_length = int(len(narrative) * reduction_factor * 0.9)  # Leave room for structured
    
    # Simple truncation - in production, use smarter pruning
    if len(narrative) > target_length:
        narrative = narrative[:target_length] + "...[truncated]"
    
    # Update exposition
    envelope.exposition.narrative = narrative
    envelope.token_budget_used = max_tokens
    
    return envelope
