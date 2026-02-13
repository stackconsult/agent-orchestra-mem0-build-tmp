# tests/test_model_router.py
"""
Tests for the model router functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from core.model_router import ModelRouter
from core.task_profiles import TaskProfile
from core.policy_engine import ScoredModel
from core.model_registry import RegisteredModel


class TestModelRouter:
    """Test cases for ModelRouter class."""
    
    @pytest.fixture
    def mock_registry(self):
        """Create a mock model registry."""
        registry = MagicMock()
        
        # Create mock models
        local_model = MagicMock()
        local_model.provider_name = "ollama"
        local_model.model_id = "llama3-8b-instruct"
        local_model.config.capabilities = ["general_qa", "planning"]
        local_model.config.max_context = 8192
        local_model.config.quality_tier = "medium"
        local_model.config.latency_tier = "medium"
        local_model.config.cost_profile.type = "local_cpu"
        local_model.config.cost_profile.relative_cost = 1.0
        
        cloud_model = MagicMock()
        cloud_model.provider_name = "anthropic"
        cloud_model.model_id = "claude-3-5-sonnet"
        cloud_model.config.capabilities = ["planning", "complex_qa"]
        cloud_model.config.max_context = 200000
        cloud_model.config.quality_tier = "very_high"
        cloud_model.config.latency_tier = "medium"
        cloud_model.config.cost_profile.type = "paid"
        cloud_model.config.cost_profile.currency = "USD"
        cloud_model.config.cost_profile.input_per_1k = 3.0
        cloud_model.config.cost_profile.output_per_1k = 15.0
        
        registry.models = [local_model, cloud_model]
        registry.get_models_by_provider.return_value = [local_model]
        registry.get_model_by_id.return_value = local_model
        registry.get_models_by_capability.return_value = [local_model, cloud_model]
        registry.get_local_models.return_value = [local_model]
        registry.get_cloud_models.return_value = [cloud_model]
        
        return registry
    
    @pytest.fixture
    def mock_policy_engine(self):
        """Create a mock policy engine."""
        engine = MagicMock()
        
        # Create mock scored model
        scored_model = ScoredModel(
            model=MagicMock(),
            score=0.5,
            reasons=["cost=1.0", "quality_rank=2", "latency_rank=2"]
        )
        scored_model.model.provider_name = "ollama"
        scored_model.model.model_id = "llama3-8b-instruct"
        
        engine.choose_best.return_value = scored_model
        engine.select_candidates.return_value = [scored_model.model]
        
        return engine
    
    @pytest.fixture
    def mock_telemetry(self):
        """Create a mock telemetry."""
        telemetry = MagicMock()
        telemetry.get_usage_summary.return_value = {
            "total_calls": 100,
            "successful_calls": 95,
            "success_rate": 0.95,
            "daily_cost": 5.50,
            "monthly_cost": 125.75,
            "model_usage": {"llama3-8b-instruct": {"calls": 60, "successes": 58}},
            "cost_by_provider": {"ollama": {"daily": 2.0, "monthly": 50.0}}
        }
        
        return telemetry
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock provider clients."""
        from unittest.mock import AsyncMock
        
        clients = {}
        
        # Mock Ollama client
        ollama_client = MagicMock()
        ollama_client.invoke = AsyncMock(return_value={
            "content": "Local model response",
            "model": "llama3-8b-instruct",
            "provider": "ollama",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        })
        ollama_client.health_check.return_value = True
        clients["ollama"] = ollama_client
        
        # Mock Anthropic client
        anthropic_client = MagicMock()
        anthropic_client.invoke = AsyncMock(return_value={
            "content": "Cloud model response",
            "model": "claude-3-5-sonnet",
            "provider": "anthropic",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        })
        anthropic_client.health_check.return_value = True
        clients["anthropic"] = anthropic_client
        
        return clients
    
    @pytest.fixture
    def router(self, mock_registry, mock_policy_engine, mock_telemetry, mock_clients):
        """Create a ModelRouter instance with mocked dependencies."""
        with patch('core.model_router.ModelRegistry', return_value=mock_registry), \
             patch('core.model_router.ModelPolicyEngine', return_value=mock_policy_engine), \
             patch('core.model_router.Telemetry', return_value=mock_telemetry), \
             patch('core.model_router.OllamaClient', return_value=mock_clients["ollama"]), \
             patch('core.model_router.OpenAIClient'), \
             patch('core.model_router.AnthropicClient', return_value=mock_clients["anthropic"]), \
             patch('core.model_router.GenericOpenAIClient'):
            
            router = ModelRouter(dry_run=False)
            router.registry = mock_registry
            router.policy_engine = mock_policy_engine
            router.telemetry = mock_telemetry
            router.clients = mock_clients
            
            return router
    
    def test_initialization(self):
        """Test router initialization."""
        router = ModelRouter(dry_run=True)
        
        assert router.dry_run is True
        assert router.registry is not None
        assert router.policy_engine is not None
        assert router.telemetry is not None
        assert len(router.clients) == 4  # ollama, openai, anthropic, generic_openai
    
    def test_plan(self, router, mock_policy_engine, mock_telemetry):
        """Test model planning (dry run)."""
        task = TaskProfile(task_type="qa", criticality="medium")
        
        result = router.plan(task)
        
        assert result is not None
        mock_policy_engine.choose_best.assert_called_once_with(task)
        mock_telemetry.record_plan.assert_called_once_with(task, result)
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_success(self, router, mock_policy_engine, mock_telemetry, mock_clients):
        """Test successful model selection and invocation."""
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        result = await router.select_and_invoke(task, messages)
        
        assert result["content"] == "Local model response"
        assert result["provider"] == "ollama"
        assert result["model"] == "llama3-8b-instruct"
        assert "routing_metadata" in result
        
        mock_policy_engine.choose_best.assert_called_once_with(task)
        mock_telemetry.before_invoke.assert_called_once()
        mock_telemetry.after_invoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_dry_run(self, router, mock_policy_engine):
        """Test model selection in dry run mode."""
        router.dry_run = True
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        result = await router.select_and_invoke(task, messages)
        
        assert result["dry_run"] is True
        assert result["provider"] == "ollama"
        assert result["model"] == "llama3-8b-instruct"
        assert "reasons" in result
        assert "score" in result
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_no_model(self, router, mock_policy_engine):
        """Test handling when no suitable model is found."""
        mock_policy_engine.choose_best.return_value = None
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        with pytest.raises(RuntimeError, match="No suitable model"):
            await router.select_and_invoke(task, messages)
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_with_fallback(self, router, mock_policy_engine, mock_telemetry, mock_clients):
        """Test fallback mechanism when primary model fails."""
        # Configure primary model to fail
        mock_clients["ollama"].invoke.side_effect = Exception("Primary model failed")
        
        # Configure fallback candidates
        fallback_model = MagicMock()
        fallback_model.provider_name = "anthropic"
        fallback_model.model_id = "claude-3-5-sonnet"
        
        mock_policy_engine.select_candidates.return_value = [
            mock_policy_engine.choose_best.return_value.model,
            fallback_model
        ]
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        result = await router.select_and_invoke(task, messages)
        
        # Should fallback to cloud model
        assert result["content"] == "Cloud model response"
        assert result["provider"] == "anthropic"
        assert result["routing_metadata"]["fallback"] is True
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_all_fallbacks_fail(self, router, mock_policy_engine, mock_clients):
        """Test handling when all models fail."""
        # Configure all models to fail
        mock_clients["ollama"].invoke.side_effect = Exception("Local model failed")
        mock_clients["anthropic"].invoke.side_effect = Exception("Cloud model failed")
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        with pytest.raises(Exception):
            await router.select_and_invoke(task, messages)
    
    @pytest.mark.asyncio
    async def test_select_and_invoke_with_tools(self, router, mock_policy_engine, mock_telemetry, mock_clients):
        """Test model invocation with tools."""
        task = TaskProfile(task_type="routing", tool_use_required=True)
        messages = [{"role": "user", "content": "test"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        
        result = await router.select_and_invoke(task, messages, tools)
        
        assert result["content"] == "Local model response"
        # Verify tools were passed to the client
        mock_clients["ollama"].invoke.assert_called_once()
        call_args = mock_clients["ollama"].invoke.call_args
        assert "tools" in call_args.kwargs
        assert call_args.kwargs["tools"] == tools
    
    def test_get_usage_summary(self, router, mock_telemetry):
        """Test getting usage summary."""
        summary = router.get_usage_summary()
        
        assert summary["total_calls"] == 100
        assert summary["success_rate"] == 0.95
        assert summary["daily_cost"] == 5.50
        assert "model_usage" in summary
        assert "cost_by_provider" in summary
        
        mock_telemetry.get_usage_summary.assert_called_once()
    
    def test_get_available_models(self, router, mock_registry):
        """Test getting available models by provider."""
        models = router.get_available_models()
        
        assert "ollama" in models
        assert "anthropic" in models
        assert len(models["ollama"]) == 1
        assert len(models["anthropic"]) == 1
    
    @pytest.mark.asyncio
    async def test_health_check(self, router, mock_clients):
        """Test health check of all providers."""
        health = await router.health_check()
        
        assert health["ollama"] is True
        assert health["anthropic"] is True
        
        # Verify all clients were checked
        mock_clients["ollama"].health_check.assert_called_once()
        mock_clients["anthropic"].health_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close(self, router, mock_clients):
        """Test closing all provider clients."""
        # Mock close methods
        mock_clients["ollama"].close = AsyncMock()
        mock_clients["anthropic"].close = AsyncMock()
        
        await router.close()
        
        # Verify close was called on clients that have it
        mock_clients["ollama"].close.assert_called_once()
        mock_clients["anthropic"].close.assert_called_once()
    
    def test_client_for_unknown_provider(self, router):
        """Test handling of unknown provider."""
        with pytest.raises(RuntimeError, match="No client configured"):
            router._client_for("unknown_provider")
    
    @pytest.mark.asyncio
    async def test_attempt_fallback_success(self, router, mock_policy_engine, mock_clients):
        """Test successful fallback attempt."""
        # Configure primary model to fail
        primary_model = mock_policy_engine.choose_best.return_value.model
        primary_model.provider_name = "ollama"
        primary_model.model_id = "llama3-8b-instruct"
        mock_clients["ollama"].invoke.side_effect = Exception("Primary failed")
        
        # Configure fallback model
        fallback_model = MagicMock()
        fallback_model.provider_name = "anthropic"
        fallback_model.model_id = "claude-3-5-sonnet"
        
        mock_policy_engine.select_candidates.return_value = [primary_model, fallback_model]
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        result = await router._attempt_fallback(task, messages)
        
        assert result is not None
        assert result["provider"] == "anthropic"
        assert result["routing_metadata"]["fallback"] is True
    
    @pytest.mark.asyncio
    async def test_attempt_fallback_all_fail(self, router, mock_policy_engine, mock_clients):
        """Test fallback attempt when all models fail."""
        # Configure all models to fail
        mock_clients["ollama"].invoke.side_effect = Exception("Local failed")
        mock_clients["anthropic"].invoke.side_effect = Exception("Cloud failed")
        
        task = TaskProfile(task_type="qa", criticality="medium")
        messages = [{"role": "user", "content": "test"}]
        
        result = await router._attempt_fallback(task, messages)
        
        assert result is None
