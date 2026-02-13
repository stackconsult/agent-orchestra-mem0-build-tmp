# main_updated.py
"""
Main entry point for the Q&A Orchestra Agent system.
Updated to use ModelRouter for local-first model selection.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from uuid import UUID

from orchestrator.orchestrator import OrchestraOrchestrator
from integrations.repo_reader import UnifiedRepositoryReader
from core.model_router import ModelRouter
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global orchestrator, model_router
    
    # Startup
    try:
        # Check if we're in dry run mode
        dry_run = os.getenv("DRY_RUN_MODE", "false").lower() == "true"
        
        # Initialize model router
        model_router = ModelRouter(dry_run=dry_run)
        
        # Check model router health
        health_status = await model_router.health_check()
        logger.info(f"Model router health status: {health_status}")
        
        # Get available models
        available_models = model_router.get_available_models()
        logger.info(f"Available models by provider: {list(available_models.keys())}")
        
        # Initialize repository reader
        repo_reader = UnifiedRepositoryReader(
            local_repo_path=os.getenv("LOCAL_REPO_PATH"),
            github_token=os.getenv("GITHUB_TOKEN"),
            repo_owner=os.getenv("GITHUB_REPO_OWNER"),
            repo_name=os.getenv("GITHUB_REPO_NAME")
        )
        
        # Initialize orchestrator with model router
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        orchestrator = OrchestraOrchestrator(model_router, redis_url)
        
        # Connect to services
        await repo_reader.connect()
        await orchestrator.start()
        
        logger.info("Q&A Orchestra Agent (Local-First) started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise
    
    # Shutdown
    try:
        if orchestrator:
            await orchestrator.stop()
        if model_router:
            await model_router.close()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


# Create FastAPI app
app = FastAPI(
    title="Q&A Orchestra Agent - Local-First",
    description="Production-grade meta-agent system with local-first model routing",
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


# Pydantic models for API
class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = None
    metadata: Optional[dict] = None


class UserInputRequest(BaseModel):
    session_id: UUID
    user_input: str
    input_type: str = "text"


class RefinementRequest(BaseModel):
    session_id: UUID
    refinement_type: str
    description: str


class ModelPlanRequest(BaseModel):
    task_type: str
    criticality: str = "medium"
    latency_sensitivity: str = "medium"
    context_size: int = 0
    tool_use_required: bool = False
    budget_sensitivity: str = "medium"


class SessionResponse(BaseModel):
    session_id: UUID
    status: str
    message: str


class UserInputResponse(BaseModel):
    status: str
    message: str
    agent_response: Optional[str] = None


# API endpoints
@app.post("/api/v1/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest):
    """Create a new design session."""
    try:
        session_id = await orchestrator.start_design_session(
            user_id=request.user_id,
            metadata=request.metadata or {}
        )
        
        return SessionResponse(
            session_id=session_id,
            status="created",
            message="Design session created successfully"
        )
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sessions/{session_id}/input", response_model=UserInputResponse)
async def process_user_input(session_id: UUID, request: UserInputRequest):
    """Process user input in a session."""
    try:
        response = await orchestrator.process_user_input(
            session_id=session_id,
            user_input=request.user_input,
            input_type=request.input_type
        )
        
        return UserInputResponse(
            status=response.get("status", "processed"),
            message=response.get("message", "Input processed"),
            agent_response=response.get("agent_response")
        )
    except Exception as e:
        logger.error(f"Failed to process user input: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sessions/{session_id}/refine", response_model=dict)
async def request_refinement(session_id: UUID, request: RefinementRequest):
    """Request a refinement to the current design."""
    try:
        response = await orchestrator.request_refinement(
            session_id=session_id,
            refinement_type=request.refinement_type,
            description=request.description
        )
        
        return response
    except Exception as e:
        logger.error(f"Failed to request refinement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/{session_id}", response_model=dict)
async def get_session_status(session_id: UUID):
    """Get session status and information."""
    try:
        status = await orchestrator.get_session_status(session_id)
        return status
    except Exception as e:
        logger.error(f"Failed to get session status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/history", response_model=list)
async def get_conversation_history(session_id: UUID, limit: Optional[int] = None):
    """Get conversation history for a session."""
    try:
        history = await orchestrator.get_conversation_history(session_id, limit)
        return history
    except Exception as e:
        logger.error(f"Failed to get conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/sessions/{session_id}", response_model=dict)
async def end_session(session_id: UUID):
    """End a session and get summary."""
    try:
        summary = await orchestrator.end_session(session_id)
        return summary
    except Exception as e:
        logger.error(f"Failed to end session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/system/status", response_model=dict)
async def get_system_status():
    """Get overall system status."""
    try:
        status = await orchestrator.get_system_status()
        
        # Add model router status
        if model_router:
            health_status = await model_router.health_check()
            usage_summary = model_router.get_usage_summary()
            available_models = model_router.get_available_models()
            
            status["model_router"] = {
                "health": health_status,
                "usage": usage_summary,
                "available_models": available_models,
                "routing_mode": os.getenv("MODEL_ROUTING_MODE", "local-preferred")
            }
        
        return status
    except Exception as e:
        logger.error(f"Failed to get system status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/models/plan", response_model=dict)
async def plan_model_selection(request: ModelPlanRequest):
    """Plan model selection for a task without invoking."""
    try:
        if not model_router:
            raise HTTPException(status_code=503, detail="Model router not available")
        
        from core.task_profiles import TaskProfile
        
        task_profile = TaskProfile(
            task_type=request.task_type,
            criticality=request.criticality,
            latency_sensitivity=request.latency_sensitivity,
            context_size=request.context_size,
            tool_use_required=request.tool_use_required,
            budget_sensitivity=request.budget_sensitivity
        )
        
        choice = model_router.plan(task_profile)
        
        if choice:
            return {
                "task_type": request.task_type,
                "selected_model": choice.model.model_id,
                "provider": choice.model.provider_name,
                "score": choice.score,
                "reasons": choice.reasons,
                "model_capabilities": choice.model.config.capabilities,
                "quality_tier": choice.model.config.quality_tier,
                "latency_tier": choice.model.config.latency_tier,
                "cost_profile": choice.model.config.cost_profile.dict()
            }
        else:
            return {
                "task_type": request.task_type,
                "selected_model": None,
                "message": "No suitable model found for this task"
            }
            
    except Exception as e:
        logger.error(f"Failed to plan model selection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/models", response_model=dict)
async def get_available_models():
    """Get all available models by provider."""
    try:
        if not model_router:
            raise HTTPException(status_code=503, detail="Model router not available")
        
        return model_router.get_available_models()
    except Exception as e:
        logger.error(f"Failed to get available models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/models/health", response_model=dict)
async def get_model_health():
    """Get health status of all model providers."""
    try:
        if not model_router:
            raise HTTPException(status_code=503, detail="Model router not available")
        
        return await model_router.health_check()
    except Exception as e:
        logger.error(f"Failed to get model health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "service": "q-and-a-orchestra-agent-local-first",
        "version": "2.0.0"
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Q&A Orchestra Agent - Local-First",
        "version": "2.0.0",
        "description": "Production-grade meta-agent system with local-first model routing",
        "features": [
            "Local-first model selection",
            "Automatic fallback to cloud models",
            "Cost-aware routing",
            "Multi-provider support (Ollama, OpenAI, Anthropic, Generic)",
            "Telemetry and usage tracking"
        ],
        "endpoints": {
            "create_session": "POST /api/v1/sessions",
            "process_input": "POST /api/v1/sessions/{session_id}/input",
            "get_status": "GET /api/v1/sessions/{session_id}",
            "get_history": "GET /api/v1/sessions/{session_id}/history",
            "request_refinement": "POST /api/v1/sessions/{session_id}/refine",
            "end_session": "DELETE /api/v1/sessions/{session_id}",
            "system_status": "GET /api/v1/system/status",
            "plan_model": "POST /api/v1/models/plan",
            "get_models": "GET /api/v1/models",
            "model_health": "GET /api/v1/models/health",
            "health": "GET /api/v1/health"
        }
    }


def main():
    """Main entry point for running the application."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Q&A Orchestra Agent - Local-First")
    parser.add_argument("--host", default=os.getenv("API_HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8000")), help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Log level")
    
    args = parser.parse_args()
    
    # Configure logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    logger.info(f"Starting Q&A Orchestra Agent (Local-First) on {args.host}:{args.port}")
    
    uvicorn.run(
        "main_updated:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level.lower()
    )


if __name__ == "__main__":
    main()
