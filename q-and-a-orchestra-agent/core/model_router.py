# core/model_router.py
from typing import List, Dict, Any, Optional
import logging
import os

from .task_profiles import TaskProfile
from .model_registry import ModelRegistry
from .policy_engine import ModelPolicyEngine, ScoredModel
from .telemetry import Telemetry
from providers.base_client import BaseModelClient
from providers.ollama_client import OllamaClient
from providers.openai_client import OpenAIClient
from providers.anthropic_client import AnthropicClient
from providers.generic_openai_client import GenericOpenAIClient

logger = logging.getLogger(__name__)


class ModelRouter:
    """Main router for model selection and invocation."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.registry = ModelRegistry()
        self.policy_engine = ModelPolicyEngine(self.registry)
        self.telemetry = Telemetry()
        
        # Initialize provider clients
        self.clients: Dict[str, BaseModelClient] = {
            "ollama": OllamaClient(),
            "openai": OpenAIClient(),
            "anthropic": AnthropicClient(),
            "generic_openai": GenericOpenAIClient(),
        }
        
        logger.info(f"ModelRouter initialized with dry_run={dry_run}")
    
    def _client_for(self, provider_name: str) -> BaseModelClient:
        """Get the appropriate client for a provider."""
        if provider_name not in self.clients:
            raise RuntimeError(f"No client configured for provider {provider_name}")
        return self.clients[provider_name]
    
    def plan(self, task: TaskProfile) -> Optional[ScoredModel]:
        """Return the selected model + reasons, no invocation."""
        try:
            choice = self.policy_engine.choose_best(task)
            self.telemetry.record_plan(task, choice)
            return choice
        except Exception as e:
            logger.error(f"Error planning model selection: {e}")
            raise
    
    async def select_and_invoke(
        self,
        task: TaskProfile,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Select and invoke the best model for a given task."""
        try:
            # Select best model
            choice = self.policy_engine.choose_best(task)
            if choice is None:
                raise RuntimeError(f"No suitable model for task={task.task_type}")
            
            # Dry run mode - just return what would happen
            if self.dry_run:
                return {
                    "dry_run": True,
                    "provider": choice.model.provider_name,
                    "model": choice.model.model_id,
                    "reasons": choice.reasons,
                    "score": choice.score,
                    "task_type": task.task_type,
                }
            
            # Get appropriate client
            client = self._client_for(choice.model.provider_name)
            
            # Record telemetry before invocation
            self.telemetry.before_invoke(task, choice)
            
            try:
                # Invoke the model
                result = await client.invoke(
                    model_id=choice.model.model_id,
                    messages=messages,
                    tools=tools,
                    **kwargs
                )
                
                # Record successful invocation
                self.telemetry.after_invoke(task, choice, success=True, result=result)
                
                # Add routing metadata to result
                result["routing_metadata"] = {
                    "provider": choice.model.provider_name,
                    "model": choice.model.model_id,
                    "score": choice.score,
                    "reasons": choice.reasons,
                    "task_type": task.task_type,
                }
                
                logger.info(f"Successfully invoked {choice.model.model_id} for {task.task_type}")
                return result
                
            except Exception as e:
                # Record failed invocation
                self.telemetry.after_invoke(task, choice, success=False, error=e)
                
                # Try fallback to next best model
                logger.warning(f"Primary model {choice.model.model_id} failed: {e}, attempting fallback")
                
                fallback_result = await self._attempt_fallback(task, messages, tools, **kwargs)
                if fallback_result:
                    return fallback_result
                
                # If no fallback worked, re-raise the original error
                raise
                
        except Exception as e:
            logger.error(f"Error in select_and_invoke: {e}")
            raise
    
    async def _attempt_fallback(
        self,
        task: TaskProfile,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Attempt to invoke fallback models."""
        try:
            # Get all candidates for the task
            candidates = self.policy_engine.select_candidates(task)
            
            # Try each candidate in order of preference (excluding the failed one)
            for candidate in candidates:
                # Skip the failed model (we already tried it)
                # In a real implementation, we'd track which model failed
                
                try:
                    client = self._client_for(candidate.provider_name)
                    
                    result = await client.invoke(
                        model_id=candidate.model_id,
                        messages=messages,
                        tools=tools,
                        **kwargs
                    )
                    
                    # Score this candidate
                    scored = self.policy_engine.score_model(candidate, task)
                    
                    # Record telemetry for fallback
                    self.telemetry.before_invoke(task, scored)
                    self.telemetry.after_invoke(task, scored, success=True, result=result)
                    
                    # Add fallback metadata
                    result["routing_metadata"] = {
                        "provider": candidate.provider_name,
                        "model": candidate.model_id,
                        "score": scored.score,
                        "reasons": scored.reasons + ["fallback_used"],
                        "task_type": task.task_type,
                        "fallback": True,
                    }
                    
                    logger.info(f"Fallback successful with {candidate.model_id}")
                    return result
                    
                except Exception as fallback_error:
                    logger.warning(f"Fallback model {candidate.model_id} also failed: {fallback_error}")
                    continue
            
            # No fallback worked
            logger.error("All fallback models failed")
            return None
            
        except Exception as e:
            logger.error(f"Error in fallback attempt: {e}")
            return None
    
    def get_usage_summary(self) -> dict:
        """Get a summary of model usage and costs."""
        return self.telemetry.get_usage_summary()
    
    def get_available_models(self) -> dict:
        """Get all available models by provider."""
        models_by_provider = {}
        
        for provider_name, client in self.clients.items():
            try:
                # This would be async in a real implementation
                # For now, get from registry
                provider_models = self.registry.get_models_by_provider(provider_name)
                models_by_provider[provider_name] = [
                    {
                        "id": model.model_id,
                        "display_name": model.config.display_name,
                        "capabilities": model.config.capabilities,
                        "max_context": model.config.max_context,
                        "quality_tier": model.config.quality_tier,
                        "latency_tier": model.config.latency_tier,
                    }
                    for model in provider_models
                ]
            except Exception as e:
                logger.error(f"Error getting models for provider {provider_name}: {e}")
                models_by_provider[provider_name] = []
        
        return models_by_provider
    
    async def health_check(self) -> dict:
        """Check health of all providers."""
        health_status = {}
        
        for provider_name, client in self.clients.items():
            try:
                health_status[provider_name] = client.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {provider_name}: {e}")
                health_status[provider_name] = False
        
        return health_status
    
    async def close(self):
        """Close all provider clients."""
        for provider_name, client in self.clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
            except Exception as e:
                logger.error(f"Error closing client {provider_name}: {e}")
        
        logger.info("All model router clients closed")
