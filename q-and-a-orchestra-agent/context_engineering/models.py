"""
Context Engineering Models - 6-Layer Framework Implementation

StackConsulting Production Pattern: 6-Layer Context Engineering
User, Intent, Domain, Rules, Environment, Exposition
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime


class UserContext(BaseModel):
    """User Layer: Who is talking, their preferences, role, expertise, and history."""
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    expertise_level: Optional[str] = None  # "beginner" | "intermediate" | "expert"
    preferences: Dict[str, Any] = Field(default_factory=dict)  # tone, detail level, etc.
    history_summary: Optional[str] = None  # short mem0 summary
    session_count: Optional[int] = None
    last_seen: Optional[datetime] = None


class IntentContext(BaseModel):
    """Intent Layer: What job are they hiring the system to do right now."""
    primary_intent: str = Field(description="Main intent category")
    task_type: Optional[str] = None
    success_criteria: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: Optional[float] = None
    escalation_path: Optional[str] = None


class DomainContext(BaseModel):
    """Domain Layer: Workspace entities, relationships, and relevant documents."""
    repo_path: Optional[str] = None
    repo_summary: Optional[str] = None
    key_components: Dict[str, str] = Field(default_factory=dict)  # name -> brief description
    related_docs: Dict[str, str] = Field(default_factory=dict)  # doc_name -> storage_key/url
    project_metadata: Dict[str, Any] = Field(default_factory=dict)
    entity_relationships: Dict[str, List[str]] = Field(default_factory=dict)


class RulesContext(BaseModel):
    """Rules Layer: Hard and soft constraints (Two-Wall System)."""
    soft_walls: Dict[str, Any] = Field(default_factory=dict)  # tone, style, best-practices
    hard_walls: Dict[str, Any] = Field(default_factory=dict)  # permissions, PII, compliance
    tenant_policies: Dict[str, Any] = Field(default_factory=dict)
    validation_schemas: Dict[str, Any] = Field(default_factory=dict)


class EnvironmentContext(BaseModel):
    """Environment Layer: Current system state and deployment context."""
    environment: str = Field(default="development")  # "development" | "staging" | "production"
    model_routing_mode: str = Field(default="local-preferred")
    feature_flags: Dict[str, bool] = Field(default_factory=dict)
    rate_limits: Dict[str, Any] = Field(default_factory=dict)
    active_sessions: int = Field(default=0)
    system_load: Optional[float] = None
    deployment_version: Optional[str] = None


class ExpositionContext(BaseModel):
    """Exposition Layer: Filtered, prioritized, structured synthesis for LLMs."""
    narrative: str = Field(description="Human-readable stitched context")
    structured: Dict[str, Any] = Field(default_factory=dict, description="Machine-usable pieces")
    token_count: Optional[int] = None
    priority_score: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContextEnvelope(BaseModel):
    """Complete context package containing all 6 layers."""
    user: UserContext
    intent: IntentContext
    domain: DomainContext
    rules: RulesContext
    environment: EnvironmentContext
    exposition: ExpositionContext
    
    # Metadata
    context_id: str = Field(description="Unique identifier for this context envelope")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    token_budget_used: Optional[int] = None
    processing_time_ms: Optional[float] = None


class ContextOverride(BaseModel):
    """Overrides for specific layers in a request."""
    override_user_preferences: Optional[Dict[str, Any]] = None
    override_intent: Optional[Dict[str, Any]] = None
    override_domain: Optional[Dict[str, Any]] = None
    override_rules: Optional[Dict[str, Any]] = None
    override_environment: Optional[Dict[str, Any]] = None


class ContextConfig(BaseModel):
    """Configuration for context building."""
    max_tokens_per_layer: Dict[str, int] = Field(
        default={
            "user": 2000,
            "intent": 1000,
            "domain": 2000,
            "rules": 1500,
            "environment": 1000,
            "exposition": 500
        }
    )
    enable_layer: Dict[str, bool] = Field(
        default={
            "user": True,
            "intent": True,
            "domain": True,
            "rules": True,
            "environment": True,
            "exposition": True
        }
    )
    source_priorities: Dict[str, int] = Field(
        default={
            "auth_claims": 100,
            "mem0": 90,
            "repo_analyzer": 80,
            "config": 70,
            "env_vars": 60
        }
    )
