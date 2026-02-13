# tests/test_model_registry.py
"""
Tests for the model registry functionality.
"""

import pytest
import tempfile
import yaml
from pathlib import Path

from core.model_registry import ModelRegistry, RegisteredModel, ModelsConfig
from core.model_registry import ModelConfig, ProviderConfig, CostProfile


class TestModelRegistry:
    """Test cases for ModelRegistry class."""
    
    @pytest.fixture
    def sample_config(self):
        """Create a sample configuration for testing."""
        return {
            "providers": {
                "ollama": {
                    "type": "local",
                    "base_url": "http://localhost:11434",
                    "discover": True,
                    "models": [
                        {
                            "id": "llama3-8b-instruct",
                            "display_name": "Llama 3 8B Instruct",
                            "capabilities": ["general_qa", "planning"],
                            "max_context": 8192,
                            "quality_tier": "medium",
                            "latency_tier": "medium",
                            "cost_profile": {
                                "type": "local_cpu",
                                "relative_cost": 1.0
                            }
                        }
                    ]
                },
                "anthropic": {
                    "type": "cloud",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "models": [
                        {
                            "id": "claude-3-5-sonnet",
                            "display_name": "Claude 3.5 Sonnet",
                            "capabilities": ["planning", "complex_qa"],
                            "max_context": 200000,
                            "quality_tier": "very_high",
                            "latency_tier": "medium",
                            "cost_profile": {
                                "type": "paid",
                                "currency": "USD",
                                "input_per_1k": 3.0,
                                "output_per_1k": 15.0
                            }
                        }
                    ]
                }
            }
        }
    
    @pytest.fixture
    def temp_config_file(self, sample_config):
        """Create a temporary configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_config, f)
            temp_path = f.name
        
        yield Path(temp_path)
        
        # Cleanup
        temp_path.unlink()
    
    def test_load_config(self, temp_config_file):
        """Test loading configuration from file."""
        registry = ModelRegistry(str(temp_config_file))
        registry.load()
        
        assert len(registry.models) == 2
        assert len([m for m in registry.models if m.provider_name == "ollama"]) == 1
        assert len([m for m in registry.models if m.provider_name == "anthropic"]) == 1
    
    def test_get_models_by_provider(self, temp_config_file):
        """Test getting models by provider."""
        registry = ModelRegistry(str(temp_config_file))
        registry.load()
        
        ollama_models = registry.get_models_by_provider("ollama")
        anthropic_models = registry.get_models_by_provider("anthropic")
        
        assert len(ollama_models) == 1
        assert len(anthropic_models) == 1
        assert ollama_models[0].model_id == "llama3-8b-instruct"
        assert anthropic_models[0].model_id == "claude-3-5-sonnet"
    
    def test_get_model_by_id(self, temp_config_file):
        """Test getting a specific model by ID."""
        registry = ModelRegistry(str(temp_config_file))
        registry.load()
        
        model = registry.get_model_by_id("llama3-8b-instruct")
        assert model is not None
        assert model.provider_name == "ollama"
        assert model.config.display_name == "Llama 3 8B Instruct"
        
        # Test non-existent model
        model = registry.get_model_by_id("non-existent")
        assert model is None
    
    def test_get_models_by_capability(self, temp_config_file):
        """Test getting models by capability."""
        registry = ModelRegistry(str(temp_config_file))
        registry.load()
        
        planning_models = registry.get_models_by_capability("planning")
        qa_models = registry.get_models_by_capability("general_qa")
        
        assert len(planning_models) == 2  # Both models support planning
        assert len(qa_models) == 1  # Only ollama model supports general_qa
    
    def test_get_local_models(self, temp_config_file):
        """Test getting local models."""
        registry = ModelRegistry(str(temp_config_file))
        registry.load()
        
        local_models = registry.get_local_models()
        cloud_models = registry.get_cloud_models()
        
        assert len(local_models) == 1
        assert len(cloud_models) == 1
        assert local_models[0].provider_name == "ollama"
        assert cloud_models[0].provider_name == "anthropic"
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        registry = ModelRegistry("non_existent_file.yaml")
        
        with pytest.raises(RuntimeError, match="Models config file not found"):
            registry.load()
    
    def test_invalid_yaml_config(self):
        """Test handling of invalid YAML configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            registry = ModelRegistry(temp_path)
            
            with pytest.raises(RuntimeError, match="Error parsing models.yaml"):
                registry.load()
        finally:
            Path(temp_path).unlink()
    
    def test_invalid_config_schema(self):
        """Test handling of invalid configuration schema."""
        invalid_config = {
            "providers": {
                "test": {
                    "type": "invalid_type",  # Invalid type
                    "models": []
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            temp_path = f.name
        
        try:
            registry = ModelRegistry(temp_path)
            
            with pytest.raises(RuntimeError, match="Invalid models.yaml"):
                registry.load()
        finally:
            Path(temp_path).unlink()


class TestConfigModels:
    """Test cases for configuration model classes."""
    
    def test_cost_profile_validation(self):
        """Test CostProfile validation."""
        # Valid local CPU profile
        profile = CostProfile(type="local_cpu", relative_cost=1.0)
        assert profile.type == "local_cpu"
        assert profile.relative_cost == 1.0
        
        # Valid paid profile
        profile = CostProfile(
            type="paid",
            currency="USD",
            input_per_1k=3.0,
            output_per_1k=15.0
        )
        assert profile.type == "paid"
        assert profile.currency == "USD"
        assert profile.input_per_1k == 3.0
        assert profile.output_per_1k == 15.0
    
    def test_model_config_validation(self):
        """Test ModelConfig validation."""
        cost_profile = CostProfile(type="local_cpu", relative_cost=1.0)
        
        model = ModelConfig(
            id="test-model",
            display_name="Test Model",
            capabilities=["general_qa"],
            max_context=4096,
            quality_tier="medium",
            latency_tier="low",
            cost_profile=cost_profile
        )
        
        assert model.id == "test-model"
        assert model.display_name == "Test Model"
        assert "general_qa" in model.capabilities
        assert model.max_context == 4096
    
    def test_provider_config_validation(self):
        """Test ProviderConfig validation."""
        cost_profile = CostProfile(type="local_cpu", relative_cost=1.0)
        model = ModelConfig(
            id="test-model",
            capabilities=["general_qa"],
            max_context=4096,
            quality_tier="medium",
            latency_tier="low",
            cost_profile=cost_profile
        )
        
        provider = ProviderConfig(
            type="local",
            base_url="http://localhost:11434",
            discover=True,
            models=[model]
        )
        
        assert provider.type == "local"
        assert provider.base_url == "http://localhost:11434"
        assert provider.discover is True
        assert len(provider.models) == 1
    
    def test_models_config_validation(self):
        """Test ModelsConfig validation."""
        cost_profile = CostProfile(type="local_cpu", relative_cost=1.0)
        model = ModelConfig(
            id="test-model",
            capabilities=["general_qa"],
            max_context=4096,
            quality_tier="medium",
            latency_tier="low",
            cost_profile=cost_profile
        )
        
        provider = ProviderConfig(
            type="local",
            models=[model]
        )
        
        models_config = ModelsConfig(providers={"test": provider})
        
        assert "test" in models_config.providers
        assert models_config.providers["test"].type == "local"
