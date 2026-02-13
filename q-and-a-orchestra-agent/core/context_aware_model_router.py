# core/context_aware_model_router.py
"""
Context-Aware Model Router - Enhanced with 6-Layer Context Engineering

Uses context engineering to make intelligent routing decisions based on
user intent, expertise, system state, and compliance requirements.
"""

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

# Import context engineering
from context_engineering.models import ContextEnvelope, RulesContext, EnvironmentContext

logger = logging.getLogger(__name__)


class ContextAwareModelRouter:
    """
    Model router that uses 6-Layer Context Engineering for routing decisions.
    """
    
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
        
        logger.info(f"ContextAwareModelRouter initialized with dry_run={dry_run}")
    
    def _client_for(self, provider_name: str) -> BaseModelClient:
        """Get the appropriate client for a provider."""
        if provider_name not in self.clients:
            raise RuntimeError(f"No client configured for provider {provider_name}")
        return self.clients[provider_name]
    
    def plan_with_context(
        self,
        task: TaskProfile,
        context_envelope: ContextEnvelope
    ) -> Optional[ScoredModel]:
        """
        Plan model selection using context engineering.
        
        Args:
            task: Task profile
            context_envelope: Complete context from 6-layer engineering
        
        Returns:
            Selected model with reasoning
        """
        try:
            # Enhance task profile with context
            enhanced_task = self._enhance_task_with_context(task, context_envelope)
            
            # Apply context-aware routing rules
            routing_decision = self._apply_context_routing(enhanced_task, context_envelope)
            
            if routing_decision.get("override_model"):
                # Use context override
                model = self.registry.get_model(routing_decision["override_model"])
                if model:
                    choice = ScoredModel(
                        model=model,
                        score=1.0,
                        reasons=routing_decision["reasons"]
                    )
                    self.telemetry.record_plan(enhanced_task, choice)
                    return choice
            
            # Use standard policy engine with enhanced task
            choice = self.policy_engine.choose_best(enhanced_task)
            
            # Apply final context filters
            if self._passes_context_filters(choice, context_envelope):
                self.telemetry.record_plan(enhanced_task, choice)
                return choice
            else:
                # Fall back to compliant model
                fallback = self._get_compliant_fallback(context_envelope)
                if fallback:
                    self.telemetry.record_plan(enhanced_task, fallback)
                    return fallback
            
            logger.warning(f"No suitable model found for task with context")
            return None
            
        except Exception as e:
            logger.error(f"Error planning model selection with context: {e}")
            raise
    
    async def select_and_invoke_with_context(
        self,
        task: TaskProfile,
        messages: List[Dict[str, Any]],
        context_envelope: ContextEnvelope,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Select and invoke model using context engineering.
        
        Args:
            task: Task profile
            messages: Message list
            context_envelope: Complete context from 6-layer engineering
            tools: Optional tools for function calling
            **kwargs: Additional invocation parameters
        
        Returns:
            Model response with context metadata
        """
        try:
            # Plan model selection with context
            choice = self.plan_with_context(task, context_envelope)
            if choice is None:
                raise RuntimeError(f"No suitable model for task={task.task_type} with context")
            
            # Dry run mode
            if self.dry_run:
                return {
                    "dry_run": True,
                    "provider": choice.model.provider_name,
                    "model": choice.model.model_id,
                    "reasons": choice.reasons,
                    "score": choice.score,
                    "task_type": task.task_type,
                    "context_id": context_envelope.context_id,
                    "routing_factors": self._get_routing_factors(context_envelope),
                }
            
            # Get appropriate client
            client = self._client_for(choice.model.provider_name)
            
            # Record telemetry before invocation
            self.telemetry.before_invoke(task, choice)
            
            # Apply context-based parameter adjustments
            invoke_params = self._adjust_parameters_with_context(
                kwargs, context_envelope, choice.model
            )
            
            try:
                # Invoke the model
                result = await client.invoke(
                    model_id=choice.model.model_id,
                    messages=messages,
                    tools=tools,
                    **invoke_params
                )
                
                # Record successful invocation
                self.telemetry.after_invoke(task, choice, success=True, result=result)
                
                # Add context metadata to result
                result["routing_metadata"] = {
                    "provider": choice.model.provider_name,
                    "model": choice.model.model_id,
                    "reasons": choice.reasons,
                    "score": choice.score,
                    "context_id": context_envelope.context_id,
                    "routing_factors": self._get_routing_factors(context_envelope),
                }
                
                # Add compliance metadata
                result["compliance_metadata"] = {
                    "rules_applied": list(context_envelope.rules.hard_walls.keys()),
                    "tenant_id": context_envelope.user.tenant_id,
                    "environment": context_envelope.environment.environment,
                }
                
                return result
                
            except Exception as e:
                # Record failed invocation
                self.telemetry.after_invoke(task, choice, success=False, error=str(e))
                raise
                
        except Exception as e:
            logger.error(f"Error in select_and_invoke_with_context: {e}")
            raise
    
    def _enhance_task_with_context(
        self,
        task: TaskProfile,
        context: ContextEnvelope
    ) -> TaskProfile:
        """Enhance task profile with context information."""
        # Adjust criticality based on intent
        if context.intent.primary_intent in ["security_analysis", "troubleshooting"]:
            task.criticality = "high"
        elif context.user.expertise_level == "beginner":
            task.criticality = "normal"
        
        # Add context constraints to task
        if context.intent.constraints:
            task.constraints.update(context.intent.constraints)
        
        # Adjust context size estimate
        task.context_size = context.token_budget_used or task.context_size
        
        # Add compliance requirements
        if context.rules.hard_walls.get("compliance_level"):
            task.compliance_requirements = [context.rules.hard_walls["compliance_level"]]
        
        return task
    
    def _apply_context_routing(
        self,
        task: TaskProfile,
        context: ContextEnvelope
    ) -> Dict[str, Any]:
        """Apply context-specific routing rules."""
        routing = {"reasons": []}
        
        # Environment-based routing
        if context.environment.environment == "production":
            routing["reasons"].append("Production environment - prefer proven models")
            if context.environment.model_routing_mode == "local-preferred":
                routing["override_model"] = "local/claude-2.1"
        
        # Expertise-based routing
        if context.user.expertise_level == "expert":
            routing["reasons"].append("Expert user - can handle advanced models")
            task.allow_advanced_models = True
        elif context.user.expertise_level == "beginner":
            routing["reasons"].append("Beginner user - prefer patient, explanatory models")
        
        # Security/compliance routing
        if "security_analysis" in context.intent.primary_intent:
            routing["reasons"].append("Security task - require compliance-approved models")
            routing["compliance_required"] = True
        
        # Budget-based routing
        if context.environment.feature_flags.get("budget_conscious", False):
            routing["reasons"].append("Budget conscious - prefer cost-effective models")
            routing["prefer_local"] = True
        
        # Load-based routing
        if context.environment.system_load and context.environment.system_load > 0.8:
            routing["reasons"].append("High system load - prefer lightweight models")
            routing["prefer_lightweight"] = True
        
        return routing
    
    def _passes_context_filters(
        self,
        choice: ScoredModel,
        context: ContextEnvelope
    ) -> bool:
        """Check if model choice passes context filters."""
        # Check hard walls
        allowed_providers = context.rules.hard_walls.get("allowed_model_providers", [])
        if allowed_providers and choice.model.provider_name not in allowed_providers:
            logger.warning(f"Model {choice.model.provider_name} not in allowed providers")
            return False
        
        # Check compliance requirements
        if context.rules.hard_walls.get("require_compliance", False):
            if not choice.model.metadata.get("compliance_approved", False):
                logger.warning(f"Model {choice.model.model_id} not compliance approved")
                return False
        
        # Check environment constraints
        if context.environment.environment == "production":
            if choice.model.metadata.get("production_ready", False) is False:
                logger.warning(f"Model {choice.model.model_id} not production ready")
                return False
        
        return True
    
    def _get_compliant_fallback(self, context: ContextEnvelope) -> Optional[ScoredModel]:
        """Get a compliant fallback model."""
        # Try local models first
        local_models = self.registry.get_models_by_provider("ollama")
        for model in local_models:
            if model.model_id == "llama2" or model.model_id == "codellama":
                return ScoredModel(
                    model=model,
                    score=0.8,
                    reasons=["Fallback compliant model"]
                )
        
        # Try approved cloud models
        approved_providers = context.rules.hard_walls.get("allowed_model_providers", ["anthropic"])
        for provider in approved_providers:
            models = self.registry.get_models_by_provider(provider)
            if models:
                return ScoredModel(
                    model=models[0],
                    score=0.7,
                    reasons=["Approved cloud fallback"]
                )
        
        return None
    
    def _adjust_parameters_with_context(
        self,
        params: Dict[str, Any],
        context: ContextEnvelope,
        model
    ) -> Dict[str, Any]:
        """Adjust invocation parameters based on context."""
        adjusted = params.copy()
        
        # Adjust temperature based on user expertise
        if context.user.expertise_level == "beginner":
            adjusted["temperature"] = min(adjusted.get("temperature", 0.7), 0.5)
        elif context.user.expertise_level == "expert":
            adjusted["temperature"] = max(adjusted.get("temperature", 0.7), 0.8)
        
        # Adjust max tokens based on intent
        if context.intent.primary_intent in ["architecture_design", "implementation"]:
            adjusted["max_tokens"] = max(adjusted.get("max_tokens", 2000), 4000)
        
        # Apply environment constraints
        max_tokens = context.rules.hard_walls.get("max_tokens_per_response")
        if max_tokens and adjusted.get("max_tokens", 0) > max_tokens:
            adjusted["max_tokens"] = max_tokens
        
        return adjusted
    
    def _get_routing_factors(self, context: ContextEnvelope) -> Dict[str, Any]:
        """Get factors that influenced routing decision."""
        return {
            "intent": context.intent.primary_intent,
            "expertise": context.user.expertise_level,
            "environment": context.environment.environment,
            "system_load": context.environment.system_load,
            "compliance_required": bool(context.rules.hard_walls),
            "tenant_id": context.user.tenant_id,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check with context awareness."""
        base_health = {
            "status": "healthy",
            "registry_size": len(self.registry.models),
            "providers": list(self.clients.keys()),
        }
        
        # Check context engineering integration
        try:
            base_health["context_engineering"] = {
                "status": "healthy",
                "features": ["intent_routing", "compliance_filtering", "expertise_adjustment"]
            }
        except Exception as e:
            base_health["context_engineering"] = {
                "status": "error",
                "error": str(e)
            }
        
        return base_health
    
    async def close(self) -> None:
        """Close all client connections."""
        for client in self.clients.values():
            if hasattr(client, 'close'):
                await client.close()
        logger.info("ContextAwareModelRouter closed")
