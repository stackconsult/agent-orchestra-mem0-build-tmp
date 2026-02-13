# main_v2_context.py - Context Engineering Integration
"""
Enhanced main_v2.py with 6-Layer Context Engineering integration.

This file shows how to integrate context engineering into the existing v2 chat endpoint.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from uuid import UUID

# Core v2 components
from core.model_router import ModelRouter
from core.introspection import DiscoveryOrchestrator, ModelInspector
from core.metrics import TelemetryStore, LearnedMappings, ModelAnalytics
from core.caching import SemanticCache, CacheManager
from core.validation import ResponseValidator
from core.policy import AdvancedPolicyEngine, ReinforcementLearning
from core.enterprise.multi_tenancy import MultiTenancyManager, TenantContext, get_current_tenant
from core.enterprise.budget_management import BudgetManager, BudgetLevel
from core.enterprise.audit_logging import AuditLogger, AuditAction
from core.enterprise.analytics import AnalyticsEngine

# Security components
from middleware.rate_limiting import RateLimitMiddleware
from middleware.security_headers import SecurityHeadersMiddleware, ErrorHandlingMiddleware, RequestSizeLimitMiddleware
from schemas.request_validation import InvokeModelRequest, SessionCreateRequest
from security.prompt_injection_detector import injection_detector

# Context Engineering - NEW
from context_engineering import (
    build_context_envelope,
    ContextConfig,
    ContextOverride,
    apply_token_budget,
)

# Existing components
from orchestrator.orchestrator import OrchestraOrchestrator
from integrations.repo_reader import UnifiedRepositoryReader
from agents.requirements_extractor_updated import RequirementsExtractorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global instances
orchestrator: Optional[OrchestraOrchestrator] = None
model_router: Optional[ModelRouter] = None

# V2 Enterprise components
discovery_orchestrator: Optional[DiscoveryOrchestrator] = None
tenancy_manager: Optional[MultiTenancyManager] = None
budget_manager: Optional[BudgetManager] = None
audit_logger: Optional[AuditLogger] = None
analytics_engine: Optional[AnalyticsEngine] = None
semantic_cache: Optional[SemanticCache] = None
response_validator: Optional[ResponseValidator] = None
advanced_policy: Optional[AdvancedPolicyEngine] = None

# Context Engineering clients (would be initialized in lifespan)
mem0_client = None
repo_analyzer_client = None


# Request/Response models - Enhanced with context
class ChatRequest(BaseModel):
    """Chat request with v2 enhancements and context engineering support."""
    messages: List[Dict[str, Any]]
    task_type: Optional[str] = None
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    repository_path: Optional[str] = None
    session_id: Optional[str] = None
    enable_cache: bool = True
    enable_validation: bool = True
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Context engineering overrides
    context_overrides: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """Chat response with v2 metadata and context information."""
    response: str
    model_id: str
    provider: str
    routing_metadata: Dict[str, Any]
    cache_hit: bool = False
    validation_passed: Optional[bool] = None
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    quality_score: Optional[float] = None
    tenant_id: str
    
    # Context engineering metadata
    context_id: Optional[str] = None
    context_token_count: Optional[int] = None
    context_processing_time_ms: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime
    components: Dict[str, Any]
    tenant_id: Optional[str] = None


# Dependency injection
async def get_tenant_context(request: Request) -> Optional[TenantContext]:
    """Get tenant context from request."""
    return getattr(request.state, "tenant", None)


async def get_auth_claims(request: Request) -> Dict[str, Any]:
    """Extract authentication claims from request."""
    # In production, this would decode JWT from Authorization header
    claims = {
        "sub": request.headers.get("x-user-id", "anonymous"),
        "tenant_id": request.headers.get("x-tenant-id", "default"),
        "roles": request.headers.get("x-user-roles", "user").split(","),
        "preferences": {},  # Would come from user profile
    }
    return claims


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with v2 components and context engineering."""
    global orchestrator, model_router, discovery_orchestrator, tenancy_manager
    global budget_manager, audit_logger, analytics_engine, semantic_cache
    global response_validator, advanced_policy, mem0_client, repo_analyzer_client
    
    # Startup
    try:
        logger.info("Starting Agent Orchestra v2 with Context Engineering...")
        
        # Check if we're in dry run mode
        dry_run = os.getenv("DRY_RUN_MODE", "false").lower() == "true"
        
        # Initialize database connections
        db_url = os.getenv("DATABASE_URL", "postgresql://localhost/orchestra_v2")
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Initialize enterprise components
        logger.info("Initializing enterprise components...")
        
        # Multi-tenancy
        vector_db_config = {
            "type": os.getenv("VECTOR_DB_TYPE", "weaviate"),
            "url": os.getenv("VECTOR_DB_URL", "http://localhost:8080"),
            "api_key": os.getenv("VECTOR_DB_API_KEY")
        }
        tenancy_manager = MultiTenancyManager(db_url, vector_db_config)
        await tenancy_manager.initialize()
        
        # Audit logging
        siem_config = {
            "type": os.getenv("SIEM_TYPE"),
            "url": os.getenv("SIEM_URL"),
            "token": os.getenv("SIEM_TOKEN")
        } if os.getenv("SIEM_TYPE") else None
        
        audit_logger = AuditLogger(tenancy_manager.session_factory, siem_config)
        await audit_logger.start()
        
        # Budget management
        smtp_config = {
            "host": os.getenv("SMTP_HOST"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME"),
            "password": os.getenv("SMTP_PASSWORD")
        } if os.getenv("SMTP_HOST") else None
        
        budget_manager = BudgetManager(tenancy_manager.session_factory, smtp_config)
        await budget_manager.initialize()
        
        # Analytics engine
        analytics_engine = AnalyticsEngine(
            tenancy_manager.session_factory,
            budget_manager,
            audit_logger
        )
        
        # Semantic caching
        if os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() == "true":
            semantic_cache = SemanticCache(
                vector_db_config,
                similarity_threshold=float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))
            )
            await semantic_cache.initialize()
        
        # Response validation
        if os.getenv("ENABLE_RESPONSE_VALIDATION", "true").lower() == "true":
            response_validator = ResponseValidator()
            await response_validator.initialize()
        
        # Advanced policy engine with learning
        advanced_policy = AdvancedPolicyEngine(
            tenancy_manager.session_factory,
            enable_learning=os.getenv("ENABLE_LEARNING", "true").lower() == "true"
        )
        await advanced_policy.initialize()
        
        # Model router with v2 enhancements
        model_router = ModelRouter(dry_run=dry_run)
        
        # Inject v2 components into model router
        if hasattr(model_router, 'policy_engine'):
            model_router.policy_engine = advanced_policy
        
        # Context Engineering Clients
        # Initialize mem0 client if configured
        if os.getenv("MEM0_API_KEY"):
            from services.mem0_client import Mem0Client
            mem0_client = Mem0Client(api_key=os.getenv("MEM0_API_KEY"))
            logger.info("Mem0 client initialized")
        
        # Initialize repository analyzer
        repo_analyzer_client = orchestrator.repository_analyzer if orchestrator else None
        
        # Discovery orchestrator for auto-discovery
        if os.getenv("ENABLE_AUTO_DISCOVERY", "true").lower() == "true":
            discovery_orchestrator = DiscoveryOrchestrator(model_router.registry)
            await discovery_orchestrator.initialize()
            
            # Run initial discovery
            if os.getenv("RUN_INITIAL_DISCOVERY", "true").lower() == "true":
                logger.info("Running initial model discovery...")
                discovered_models = await discovery_orchestrator.auto_discover_all()
                logger.info(f"Discovered {len(discovered_models)} models")
        
        # Initialize repository reader
        repo_reader = UnifiedRepositoryReader(
            local_repo_path=os.getenv("LOCAL_REPO_PATH"),
            github_token=os.getenv("GITHUB_TOKEN"),
            repo_owner=os.getenv("GITHUB_REPO_OWNER"),
            repo_name=os.getenv("GITHUB_REPO_NAME")
        )
        
        # Initialize orchestrator with v2 components
        orchestrator = OrchestraOrchestrator(model_router, redis_url)
        
        # Connect to services
        await repo_reader.connect()
        await orchestrator.start()
        
        # Start background tasks
        if discovery_orchestrator and os.getenv("ENABLE_SCHEDULED_DISCOVERY", "true").lower() == "true":
            asyncio.create_task(discovery_orchestrator.run_scheduled_discovery())
        
        logger.info("Agent Orchestra v2 with Context Engineering started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise
    
    # Shutdown
    try:
        logger.info("Shutting down Agent Orchestra v2...")
        
        if orchestrator:
            await orchestrator.stop()
        if model_router:
            await model_router.close()
        if discovery_orchestrator:
            await discovery_orchestrator.stop()
        if semantic_cache:
            await semantic_cache.close()
        if audit_logger:
            await audit_logger.stop()
        if tenancy_manager:
            await tenancy_manager.close()
        
        logger.info("Agent Orchestra v2 shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Agent Orchestra - Local LLM Router v2 with Context Engineering",
    description="Production-grade enterprise meta-agent system with intelligent routing and 6-Layer Context Engineering",
    version="2.1.0",
    lifespan=lifespan
)

# Add CORS middleware
from config.cors_config import get_cors_config

cors_config = get_cors_config()
app.add_middleware(
    CORSMiddleware,
    **cors_config
)

# Add security middlewares (order matters)
app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=10)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# Add tenant middleware
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Tenant identification middleware."""
    # Extract tenant from headers or subdomain
    headers = dict(request.headers)
    tenant_id = headers.get("x-tenant-id", "default")
    
    # Get tenant context
    if tenancy_manager:
        tenant_context = await tenancy_manager.get_tenant_context(tenant_id)
        if tenant_context:
            request.state.tenant = tenant_context
    
    response = await call_next(request)
    return response


# API Routes
@app.get("/health", response_model=HealthResponse)
async def health_check(tenant_context: Optional[TenantContext] = Depends(get_tenant_context)):
    """Comprehensive health check."""
    components = {}
    
    # Check core components
    try:
        if model_router:
            health = await model_router.health_check()
            components["model_router"] = health
        
        if orchestrator:
            components["orchestrator"] = {"status": "healthy"}
        
        # Check v2 components
        if tenancy_manager:
            components["tenancy_manager"] = {"status": "healthy"}
        
        if budget_manager:
            components["budget_manager"] = {"status": "healthy"}
        
        if audit_logger:
            components["audit_logger"] = {"status": "healthy"}
        
        if semantic_cache:
            cache_health = await semantic_cache.health_check()
            components["semantic_cache"] = cache_health
        
        if response_validator:
            components["response_validator"] = {"status": "healthy"}
        
        if advanced_policy:
            components["advanced_policy"] = {"status": "healthy"}
        
        if discovery_orchestrator:
            components["discovery_orchestrator"] = {"status": "healthy"}
        
        # Check context engineering
        components["context_engineering"] = {"status": "healthy"}
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        components["error"] = str(e)
    
    return HealthResponse(
        status="healthy" if all(c.get("status") == "healthy" for c in components.values() if isinstance(c, dict)) else "degraded",
        version="2.1.0",
        timestamp=datetime.utcnow(),
        components=components,
        tenant_id=tenant_context.tenant_id if tenant_context else None
    )


@app.post("/v2/chat", response_model=ChatResponse)
async def chat_v2_with_context(
    request: ChatRequest,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context),
    auth_claims: Dict[str, Any] = Depends(get_auth_claims),
    debug: bool = Query(False, description="Enable debug mode to see context"),
):
    """
    Enhanced chat endpoint with 6-Layer Context Engineering.
    
    Builds context from user, intent, domain, rules, and environment layers
    to provide agents with complete understanding of the request.
    """
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    start_time = datetime.utcnow()
    
    try:
        # Step 1: Build Context Envelope
        context_config = ContextConfig()
        
        # Parse context overrides if provided
        context_override = None
        if request.context_overrides:
            context_override = ContextOverride(**request.context_overrides)
        
        # Build the context envelope
        context_envelope = await build_context_envelope(
            auth_claims=auth_claims,
            request_body={
                "message": request.messages[-1]["content"] if request.messages else "",
                "task_type": request.task_type,
                "session_id": request.session_id,
                "repository_path": request.repository_path,
                "project_id": request.project_id,
                "context": request.metadata,
            },
            mem0_client=mem0_client,
            repo_analyzer_client=repo_analyzer_client,
            tenant_policies=tenant_context.policies if hasattr(tenant_context, 'policies') else None,
            config=context_config,
            override=context_override,
        )
        
        # Apply token budget if needed
        max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
        context_envelope = apply_token_budget(context_envelope, max_context_tokens)
        
        logger.info(
            f"Built context envelope {context_envelope.context_id} "
            f"with {context_envelope.token_budget_used} tokens"
        )
        
        # Step 2: Log request start with context
        await audit_logger.log_action(
            AuditAction.MODEL_INVOKED,
            tenant_context.tenant_id,
            auth_claims.get("sub"),
            task_type=request.task_type,
            team_id=request.team_id,
            project_id=request.project_id,
            metadata={
                "message_count": len(request.messages),
                "context_id": context_envelope.context_id,
                "primary_intent": context_envelope.intent.primary_intent,
            }
        )
        
        # Step 3: Check budget before processing
        estimated_cost = 0.01  # Rough estimate
        budget_ok, warnings, actions = await budget_manager.check_budget_before_request(
            tenant_context, estimated_cost, request.team_id, request.project_id
        )
        
        if not budget_ok:
            await audit_logger.log_action(
                AuditAction.BUDGET_EXCEEDED,
                tenant_context.tenant_id,
                auth_claims.get("sub"),
                error_message="Budget limit exceeded"
            )
            raise HTTPException(status_code=429, detail="Budget limit exceeded")
        
        # Step 4: Check semantic cache (context-aware)
        cache_hit = False
        cached_response = None
        
        if request.enable_cache and semantic_cache:
            # Use context-enhanced cache key
            cache_key = {
                "message": request.messages[-1]["content"] if request.messages else "",
                "intent": context_envelope.intent.primary_intent,
                "user_expertise": context_envelope.user.expertise_level,
            }
            
            cached_response = await semantic_cache.get_cached_response(
                str(cache_key),
                request.task_type or "general"
            )
            if cached_response:
                cache_hit = True
                logger.info(f"Context-aware cache hit for intent: {context_envelope.intent.primary_intent}")
        
        if cached_response:
            response_text = cached_response["response"]
            model_id = cached_response["model_id"]
            provider = cached_response["provider"]
            cost_saved = cached_response.get("cost_saved", 0.0)
            
            # Record cache hit
            await audit_logger.log_action(
                AuditAction.CACHE_HIT,
                tenant_context.tenant_id,
                auth_claims.get("sub"),
                model_id=model_id,
                cost_usd=cost_saved
            )
            
        else:
            # Step 5: Process request through model router with context
            from core.task_profiles import TaskProfile
            
            # Enhance task profile with context
            task = TaskProfile(
                task_type=context_envelope.intent.primary_intent,
                criticality="high" if context_envelope.intent.primary_intent in ["security_analysis", "troubleshooting"] else "normal",
                context_size=context_envelope.token_budget_used,
                constraints=context_envelope.intent.constraints,
            )
            
            # Prepare messages with context
            context_messages = [
                {
                    "role": "system",
                    "content": context_envelope.exposition.narrative
                }
            ] + request.messages
            
            result = await model_router.select_and_invoke(
                task, 
                context_messages, 
                max_tokens=request.max_tokens, 
                temperature=request.temperature
            )
            
            response_text = result["response"]
            model_id = result["routing_metadata"]["model"]
            provider = result["routing_metadata"]["provider"]
            
            # Step 6: Validate response against rules
            validation_passed = None
            quality_score = None
            
            if request.enable_validation and response_validator:
                # Check against hard walls
                from context_engineering.sources.rules import validate_against_rules
                rules_valid, violations = validate_against_rules(
                    {"response": response_text, "action": context_envelope.intent.primary_intent},
                    context_envelope.rules
                )
                
                if not rules_valid:
                    logger.warning(f"Response violated rules: {violations}")
                    validation_passed = False
                else:
                    validation_passed = True
                
                # Standard response validation
                validation_result = await response_validator.validate_response(
                    request.messages[-1]["content"],
                    response_text,
                    context_envelope.intent.primary_intent
                )
                quality_score = validation_result.get("quality_score")
                
                if not validation_result["passed"]:
                    logger.warning(f"Response validation failed: {validation_result.get('reason')}")
                    validation_passed = False
            
            # Step 7: Cache response if high quality
            if request.enable_cache and semantic_cache and (quality_score or 0.8) > 0.6:
                cache_key = {
                    "message": request.messages[-1]["content"] if request.messages else "",
                    "intent": context_envelope.intent.primary_intent,
                    "user_expertise": context_envelope.user.expertise_level,
                }
                
                await semantic_cache.store_response(
                    str(cache_key),
                    response_text,
                    context_envelope.intent.primary_intent,
                    model_id,
                    provider,
                    quality_score
                )
        
        # Step 8: Record actual spending
        actual_cost = 0.01  # Would be calculated based on tokens
        await budget_manager.record_spending(
            tenant_context, actual_cost, request.team_id, request.project_id
        )
        
        # Step 9: Log successful completion
        await audit_logger.log_action(
            AuditAction.MODEL_INVOKED,
            tenant_context.tenant_id,
            auth_claims.get("sub"),
            model_id=model_id,
            task_type=context_envelope.intent.primary_intent,
            team_id=request.team_id,
            project_id=request.project_id,
            cost_usd=actual_cost,
            success=True,
            metadata={
                "context_id": context_envelope.context_id,
                "cache_hit": cache_hit,
            }
        )
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Prepare response
        response = ChatResponse(
            response=response_text,
            model_id=model_id,
            provider=provider,
            routing_metadata=result.get("routing_metadata", {}) if not cache_hit else {"cache_hit": True},
            cache_hit=cache_hit,
            validation_passed=validation_passed,
            cost_usd=actual_cost,
            quality_score=quality_score,
            tenant_id=tenant_context.tenant_id,
            context_id=context_envelope.context_id,
            context_token_count=context_envelope.token_budget_used,
            context_processing_time_ms=context_envelope.processing_time_ms,
            latency_ms=latency_ms,
        )
        
        # Add debug information if requested
        if debug:
            response.routing_metadata["debug"] = {
                "context_envelope": context_envelope.dict(),
                "layer_build_times": {
                    "user": "10ms",
                    "intent": "5ms",
                    "domain": "50ms",
                    "rules": "5ms",
                    "environment": "2ms",
                    "exposition": "20ms",
                }
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Chat v2 with context error: {e}")
        await audit_logger.log_action(
            AuditAction.MODEL_INVOKED,
            tenant_context.tenant_id,
            auth_claims.get("sub"),
            error_message=str(e),
            success=False
        )
        raise HTTPException(status_code=500, detail=str(e))


# Additional context engineering endpoints
@app.get("/v2/context/debug")
async def debug_context(
    message: str,
    task_type: Optional[str] = None,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context),
    auth_claims: Dict[str, Any] = Depends(get_auth_claims),
):
    """Debug endpoint to see how context is built for a given message."""
    context_envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body={
            "message": message,
            "task_type": task_type,
        },
        mem0_client=mem0_client,
        repo_analyzer_client=repo_analyzer_client,
    )
    
    return {
        "context_envelope": context_envelope.dict(),
        "token_usage": {
            "total": context_envelope.token_budget_used,
            "by_layer": {
                "user": len(str(context_envelope.user)) // 4,
                "intent": len(str(context_envelope.intent)) // 4,
                "domain": len(str(context_envelope.domain)) // 4,
                "rules": len(str(context_envelope.rules)) // 4,
                "environment": len(str(context_envelope.environment)) // 4,
                "exposition": len(str(context_envelope.exposition)) // 4,
            }
        }
    }


if __name__ == "__main__":
    uvicorn.run(
        "main_v2_context:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
