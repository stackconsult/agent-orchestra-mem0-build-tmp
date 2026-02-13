# main_v2.py
"""
Main entry point for Agent Orchestra Local LLM Router v2.

Production-grade enterprise system with:
- Auto-discovery and introspection
- Real-time metrics and learning
- Semantic caching and validation
- Multi-tenancy and budget management
- Audit logging and analytics
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends
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


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request with v2 enhancements."""
    messages: List[Dict[str, Any]]
    task_type: Optional[str] = None
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    enable_cache: bool = True
    enable_validation: bool = True
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Chat response with v2 metadata."""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with v2 components."""
    global orchestrator, model_router, discovery_orchestrator, tenancy_manager
    global budget_manager, audit_logger, analytics_engine, semantic_cache
    global response_validator, advanced_policy
    
    # Startup
    try:
        logger.info("Starting Agent Orchestra v2...")
        
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
        
        logger.info("Agent Orchestra v2 started successfully")
        
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
    title="Agent Orchestra - Local LLM Router v2",
    description="Production-grade enterprise meta-agent system with intelligent routing",
    version="2.0.0",
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
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        components["error"] = str(e)
    
    return HealthResponse(
        status="healthy" if all(c.get("status") == "healthy" for c in components.values() if isinstance(c, dict)) else "degraded",
        version="2.0.0",
        timestamp=datetime.utcnow(),
        components=components,
        tenant_id=tenant_context.tenant_id if tenant_context else None
    )


@app.post("/v2/chat", response_model=ChatResponse)
async def chat_v2(
    request: ChatRequest,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context)
):
    """Enhanced chat endpoint with v2 features."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        # Log request start
        await audit_logger.log_action(
            AuditAction.MODEL_INVOKED,
            tenant_context.tenant_id,
            tenant_context.user_id,
            task_type=request.task_type,
            team_id=request.team_id,
            project_id=request.project_id,
            metadata={"message_count": len(request.messages)}
        )
        
        # Check budget before processing
        estimated_cost = 0.01  # Rough estimate
        budget_ok, warnings, actions = await budget_manager.check_budget_before_request(
            tenant_context, estimated_cost, request.team_id, request.project_id
        )
        
        if not budget_ok:
            await audit_logger.log_action(
                AuditAction.BUDGET_EXCEEDED,
                tenant_context.tenant_id,
                tenant_context.user_id,
                error_message="Budget limit exceeded"
            )
            raise HTTPException(status_code=429, detail="Budget limit exceeded")
        
        # Apply budget actions (e.g., downgrade to local)
        if "downgrade_to_local" in actions:
            # Modify request to prefer local models
            pass
        
        # Check semantic cache
        cache_hit = False
        cached_response = None
        
        if request.enable_cache and semantic_cache:
            cached_response = await semantic_cache.get_cached_response(
                request.messages[-1]["content"],  # Use last message as prompt
                request.task_type or "general"
            )
            if cached_response:
                cache_hit = True
                logger.info(f"Cache hit for task: {request.task_type}")
        
        if cached_response:
            response_text = cached_response["response"]
            model_id = cached_response["model_id"]
            provider = cached_response["provider"]
            cost_saved = cached_response.get("cost_saved", 0.0)
            
            # Record cache hit
            await audit_logger.log_action(
                AuditAction.CACHE_HIT,
                tenant_context.tenant_id,
                tenant_context.user_id,
                model_id=model_id,
                cost_usd=cost_saved
            )
            
        else:
            # Process request through model router
            from core.task_profiles import TaskProfile
            
            task = TaskProfile(
                task_type=request.task_type or "general",
                criticality="normal",
                context_size=len(str(request.messages))
            )
            
            result = await model_router.select_and_invoke(
                task, request.messages, max_tokens=request.max_tokens, temperature=request.temperature
            )
            
            response_text = result["response"]
            model_id = result["routing_metadata"]["model"]
            provider = result["routing_metadata"]["provider"]
            
            # Validate response if enabled
            validation_passed = None
            quality_score = None
            
            if request.enable_validation and response_validator:
                validation_result = await response_validator.validate_response(
                    request.messages[-1]["content"],
                    response_text,
                    request.task_type or "general"
                )
                validation_passed = validation_result["passed"]
                quality_score = validation_result.get("quality_score")
                
                if not validation_passed:
                    logger.warning(f"Response validation failed: {validation_result.get('reason')}")
            
            # Cache response if high quality
            if request.enable_cache and semantic_cache and (quality_score or 0.8) > 0.6:
                await semantic_cache.store_response(
                    request.messages[-1]["content"],
                    response_text,
                    request.task_type or "general",
                    model_id,
                    provider,
                    quality_score
                )
        
        # Record actual spending
        actual_cost = 0.01  # Would be calculated based on tokens
        await budget_manager.record_spending(
            tenant_context, actual_cost, request.team_id, request.project_id
        )
        
        # Log successful completion
        await audit_logger.log_action(
            AuditAction.MODEL_INVOKED,
            tenant_context.tenant_id,
            tenant_context.user_id,
            model_id=model_id,
            task_type=request.task_type,
            team_id=request.team_id,
            project_id=request.project_id,
            cost_usd=actual_cost,
            success=True
        )
        
        return ChatResponse(
            response=response_text,
            model_id=model_id,
            provider=provider,
            routing_metadata=result.get("routing_metadata", {}) if not cache_hit else {"cache_hit": True},
            cache_hit=cache_hit,
            validation_passed=validation_passed,
            cost_usd=actual_cost,
            quality_score=quality_score,
            tenant_id=tenant_context.tenant_id
        )
        
    except Exception as e:
        logger.error(f"Chat v2 error: {e}")
        
        # Log error
        await audit_logger.log_action(
            AuditAction.MODEL_FAILED,
            tenant_context.tenant_id,
            tenant_context.user_id,
            error_message=str(e),
            success=False
        )
        
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/models")
async def list_models_v2(tenant_context: Optional[TenantContext] = Depends(get_tenant_context)):
    """List available models with v2 enhancements."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        # Get all available models
        all_models = model_router.get_available_models()
        
        # Filter based on tenant configuration
        tenant_config = tenant_context.tenant_config
        filtered_models = {}
        
        for provider, models in all_models.items():
            filtered_models[provider] = []
            
            for model in models:
                # Check if model is allowed for tenant
                if tenant_config.allowed_models and model.model_id not in tenant_config.allowed_models:
                    continue
                
                # Check if model is blocked for tenant
                if model.model_id in tenant_config.blocked_models:
                    continue
                
                filtered_models[provider].append(model)
        
        return {
            "tenant_id": tenant_context.tenant_id,
            "models": filtered_models,
            "total_count": sum(len(models) for models in filtered_models.values())
        }
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/analytics/dashboard")
async def get_analytics_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context)
):
    """Get tenant analytics dashboard."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        from datetime import datetime
        
        # Parse dates
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        
        dashboard = await analytics_engine.get_tenant_dashboard(
            tenant_context.tenant_id,
            start_dt.date() if start_dt else None,
            end_dt.date() if end_dt else None
        )
        
        return dashboard.to_dict() if dashboard else {}
        
    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/budget/status")
async def get_budget_status(tenant_context: Optional[TenantContext] = Depends(get_tenant_context)):
    """Get current budget status."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        from core.enterprise.budget_management import BudgetLevel
        
        # Get tenant-level budget status
        status = await budget_manager.get_budget_status(
            tenant_context.tenant_id, BudgetLevel.TENANT
        )
        
        return status.to_dict() if status else {}
        
    except Exception as e:
        logger.error(f"Error getting budget status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v2/discovery/run")
async def run_discovery(tenant_context: Optional[TenantContext] = Depends(get_tenant_context)):
    """Trigger model discovery."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        if not discovery_orchestrator:
            raise HTTPException(status_code=501, detail="Discovery not available")
        
        # Run discovery
        discovered_models = await discovery_orchestrator.auto_discover_all()
        
        await audit_logger.log_action(
            AuditAction.MODEL_SELECTED,
            tenant_context.tenant_id,
            tenant_context.user_id,
            metadata={"discovered_count": len(discovered_models)}
        )
        
        return {
            "discovered_models": len(discovered_models),
            "models": [model.to_dict() for model in discovered_models]
        }
        
    except Exception as e:
        logger.error(f"Error running discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v2/recommendations")
async def get_recommendations(tenant_context: Optional[TenantContext] = Depends(get_tenant_context)):
    """Get optimization recommendations."""
    if not tenant_context:
        raise HTTPException(status_code=400, detail="Tenant context required")
    
    try:
        recommendations = await analytics_engine.generate_recommendations(
            tenant_context.tenant_id
        )
        
        return {
            "tenant_id": tenant_context.tenant_id,
            "recommendations": [rec.to_dict() for rec in recommendations]
        }
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy v1 endpoints for backward compatibility
@app.post("/v1/chat")
async def chat_v1_legacy(request: ChatRequest):
    """Legacy v1 chat endpoint for backward compatibility."""
    # Route through v2 system with default tenant
    default_tenant = await tenancy_manager.get_tenant_context("default") if tenancy_manager else None
    
    # Create a mock tenant context for v1
    if not default_tenant:
        from core.enterprise.multi_tenancy import TenantConfig
        mock_config = TenantConfig(tenant_id="default", tenant_name="Default", display_name="Default")
        default_tenant = TenantContext(tenant_id="default", tenant_config=mock_config)
    
    return await chat_v2(request, default_tenant)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main_v2:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info"
    )
