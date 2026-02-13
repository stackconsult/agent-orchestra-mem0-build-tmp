# tests/test_policy_engine.py
"""
Tests for the policy engine functionality.
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from core.model_registry import ModelRegistry, CostProfile, ModelConfig, ProviderConfig
from core.policy_engine import ModelPolicyEngine, ScoredModel
from core.task_profiles import TaskProfile


class TestModelPolicyEngine:
    """Test cases for ModelPolicyEngine class."""
    
    @pytest.fixture
    def sample_models(self):
        """Create sample models for testing."""
        cost_local = CostProfile(type="local_cpu", relative_cost=1.0)
        cost_cloud = CostProfile(
            type="paid",
            currency="USD",
            input_per_1k=3.0,
            output_per_1k=15.0
        )
        
        # Local model
        local_config = ModelConfig(
            id="llama3-8b-instruct",
            display_name="Llama 3 8B Instruct",
            capabilities=["general_qa", "planning"],
            max_context=8192,
            quality_tier="medium",
            latency_tier="medium",
            cost_profile=cost_local
        )
        
        local_provider = ProviderConfig(
            type="local",
            base_url="http://localhost:11434",
            models=[local_config]
        )
        
        # Cloud model
        cloud_config = ModelConfig(
            id="claude-3-5-sonnet",
            display_name="Claude 3.5 Sonnet",
            capabilities=["planning", "complex_qa", "multi_agent_orchestration"],
            max_context=200000,
            quality_tier="very_high",
            latency_tier="medium",
            cost_profile=cost_cloud
        )
        
        cloud_provider = ProviderConfig(
            type="cloud",
            api_key_env="ANTHROPIC_API_KEY",
            models=[cloud_config]
        )
        
        return {
            "providers": {
                "ollama": local_provider,
                "anthropic": cloud_provider
            }
        }
    
    @pytest.fixture
    def mock_registry(self, sample_models):
        """Create a mock model registry."""
        registry = ModelRegistry()
        registry._raw_config = sample_models
        registry._models = []
        
        # Add models to registry
        for provider_name, provider in sample_models["providers"].items():
            for model in provider.models:
                from core.model_registry import RegisteredModel
                registry._models.append(
                    RegisteredModel(
                        provider_name=provider_name,
                        model_id=model.id,
                        config=model,
                        provider=provider
                    )
                )
        
        return registry
    
    @pytest.fixture
    def sample_policies(self):
        """Create sample policies for testing."""
        return {
            "routing": {
                "default_mode": "local-preferred",
                "modes": {
                    "local-only": {"allow_cloud": False},
                    "local-preferred": {"allow_cloud": True},
                    "balanced": {"allow_cloud": True},
                    "performance": {"allow_cloud": True}
                },
                "weights": {
                    "local-preferred": {"cost": 0.6, "quality": 0.25, "latency": 0.15},
                    "balanced": {"cost": 0.4, "quality": 0.4, "latency": 0.2},
                    "performance": {"cost": 0.2, "quality": 0.6, "latency": 0.2}
                }
            },
            "task_overrides": {
                "planning": {
                    "preferred_capabilities": ["planning", "multi_agent_orchestration"]
                },
                "routing": {
                    "preferred_providers": ["ollama"],
                    "preferred_capabilities": ["routing", "classification"]
                }
            },
            "budgets": {
                "daily": {"total_usd": 10.0},
                "monthly": {"total_usd": 150.0}
            },
            "behavior_on_budget_exceeded": {"default": "downgrade_to_local"},
            "timeouts": {"default": 60, "high_latency_ok": 120, "low_latency_required": 15}
        }
    
    @pytest.fixture
    def temp_policies_file(self, sample_policies):
        """Create a temporary policies file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_policies, f)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        temp_path.unlink()
    
    def test_select_candidates_basic(self, mock_registry, temp_policies_file):
        """Test basic candidate selection."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        task = TaskProfile(task_type="qa", criticality="medium")
        candidates = engine.select_candidates(task)
        
        # Should find models that support general_qa
        assert len(candidates) >= 1
        assert any(m.model_id == "llama3-8b-instruct" for m in candidates)
    
    def test_select_candidates_with_context_requirement(self, mock_registry, temp_policies_file):
        """Test candidate selection with context size requirements."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Require large context that only cloud model supports
        task = TaskProfile(task_type="planning", context_size=100000)
        candidates = engine.select_candidates(task)
        
        # Should only include Claude with large context
        assert len(candidates) == 1
        assert candidates[0].model_id == "claude-3-5-sonnet"
    
    def test_select_candidates_local_only_mode(self, mock_registry, temp_policies_file):
        """Test candidate selection in local-only mode."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Override mode to local-only
        engine.policies["routing"]["default_mode"] = "local-only"
        
        task = TaskProfile(task_type="planning", criticality="medium")
        candidates = engine.select_candidates(task)
        
        # Should only include local models
        assert all(m.provider_name == "ollama" for m in candidates)
    
    def test_select_candidates_with_task_overrides(self, mock_registry, temp_policies_file):
        """Test candidate selection with task overrides."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        task = TaskProfile(task_type="routing", criticality="medium")
        candidates = engine.select_candidates(task)
        
        # Should prefer ollama provider due to task override
        assert all(m.provider_name == "ollama" for m in candidates)
    
    def test_score_model(self, mock_registry, temp_policies_file):
        """Test model scoring."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Get a model to score
        local_model = mock_registry.get_model_by_id("llama3-8b-instruct")
        task = TaskProfile(task_type="qa", criticality="medium")
        
        scored = engine.score_model(local_model, task)
        
        assert isinstance(scored, ScoredModel)
        assert scored.model == local_model
        assert isinstance(scored.score, float)
        assert isinstance(scored.reasons, list)
        assert len(scored.reasons) > 0
    
    def test_choose_best_basic(self, mock_registry, temp_policies_file):
        """Test basic best model selection."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        task = TaskProfile(task_type="qa", criticality="medium")
        best = engine.choose_best(task)
        
        assert best is not None
        assert isinstance(best, ScoredModel)
        assert best.model.model_id in ["llama3-8b-instruct", "claude-3-5-sonnet"]
    
    def test_choose_best_no_candidates(self, mock_registry, temp_policies_file):
        """Test best model selection with no candidates."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Create a task that no model can handle
        task = TaskProfile(task_type="vision", criticality="medium")
        best = engine.choose_best(task)
        
        assert best is None
    
    def test_choose_best_local_preferred_mode(self, mock_registry, temp_policies_file):
        """Test model selection in local-preferred mode."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        task = TaskProfile(task_type="planning", criticality="medium")
        best = engine.choose_best(task)
        
        # In local-preferred mode, should prefer local model for planning
        # if it supports the capability
        assert best.model.provider_name == "ollama"
        assert best.model.model_id == "llama3-8b-instruct"
    
    def test_choose_best_performance_mode(self, mock_registry, temp_policies_file):
        """Test model selection in performance mode."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Override to performance mode
        engine.policies["routing"]["default_mode"] = "performance"
        
        task = TaskProfile(task_type="planning", criticality="high")
        best = engine.choose_best(task)
        
        # In performance mode, should prefer higher quality model
        assert best.model.provider_name == "anthropic"
        assert best.model.model_id == "claude-3-5-sonnet"
    
    def test_missing_policies_file(self, mock_registry):
        """Test handling of missing policies file."""
        engine = ModelPolicyEngine(mock_registry, "non_existent_policies.yaml")
        
        # Should use default policies
        assert engine.policies is not None
        assert "routing" in engine.policies
        assert engine.policies["routing"]["default_mode"] == "local-preferred"
    
    def test_invalid_policies_file(self, mock_registry):
        """Test handling of invalid policies file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            engine = ModelPolicyEngine(mock_registry, temp_path)
            
            # Should use default policies
            assert engine.policies is not None
            assert engine.policies["routing"]["default_mode"] == "local-preferred"
        finally:
            Path(temp_path).unlink()
    
    def test_weights_calculation(self, mock_registry, temp_policies_file):
        """Test weight calculation for different modes."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Test local-preferred weights
        engine.policies["routing"]["default_mode"] = "local-preferred"
        weights = engine._weights()
        
        assert weights["cost"] > weights["quality"]
        assert weights["cost"] > weights["latency"]
        
        # Test performance weights
        engine.policies["routing"]["default_mode"] = "performance"
        weights = engine._weights()
        
        assert weights["quality"] > weights["cost"]
        assert weights["quality"] > weights["latency"]
    
    def test_capability_filtering(self, mock_registry, temp_policies_file):
        """Test filtering by capabilities."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Task requiring complex_qa - only Claude supports this
        task = TaskProfile(task_type="qa", criticality="high")
        candidates = engine.select_candidates(task)
        
        # Should include Claude for complex tasks
        assert any(m.model_id == "claude-3-5-sonnet" for m in candidates)
    
    def test_context_size_filtering(self, mock_registry, temp_policies_file):
        """Test filtering by context size."""
        engine = ModelPolicyEngine(mock_registry, str(temp_policies_file))
        
        # Task requiring more context than local model supports
        task = TaskProfile(task_type="planning", context_size=10000)
        candidates = engine.select_candidates(task)
        
        # Should only include models with sufficient context
        for candidate in candidates:
            assert candidate.config.max_context >= 10000
