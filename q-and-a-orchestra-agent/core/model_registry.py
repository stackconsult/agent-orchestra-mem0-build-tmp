# core/model_registry.py
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Any
from pathlib import Path
import logging

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class CostProfile(BaseModel):
    type: Literal["local_cpu", "paid"]
    relative_cost: Optional[float] = None
    currency: Optional[str] = "USD"
    input_per_1k: Optional[float] = None
    output_per_1k: Optional[float] = None


class ModelConfig(BaseModel):
    id: str
    display_name: Optional[str] = None
    capabilities: List[str]
    max_context: int
    quality_tier: str
    latency_tier: str
    cost_profile: CostProfile


class ProviderConfig(BaseModel):
    type: Literal["local", "cloud"]
    base_url: Optional[str] = None
    base_url_env: Optional[str] = None
    api_key_env: Optional[str] = None
    discover: bool = False
    models: List[ModelConfig]


class ModelsConfig(BaseModel):
    providers: Dict[str, ProviderConfig]


@dataclass
class RegisteredModel:
    provider_name: str
    model_id: str
    config: ModelConfig
    provider: ProviderConfig


class ModelRegistry:
    def __init__(self, config_path: str = "config/models.yaml"):
        self.config_path = Path(config_path)
        self._raw_config: Optional[ModelsConfig] = None
        self._models: List[RegisteredModel] = []

    def load(self) -> None:
        """Load model configuration from YAML file."""
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self._raw_config = ModelsConfig.model_validate(data)
        except FileNotFoundError:
            raise RuntimeError(f"Models config file not found: {self.config_path}")
        except ValidationError as e:
            raise RuntimeError(f"Invalid models.yaml: {e}") from e
        except yaml.YAMLError as e:
            raise RuntimeError(f"Error parsing models.yaml: {e}") from e

        self._models.clear()
        for provider_name, provider in self._raw_config.providers.items():
            for model in provider.models:
                self._models.append(
                    RegisteredModel(
                        provider_name=provider_name,
                        model_id=model.id,
                        config=model,
                        provider=provider,
                    )
                )
        
        logger.info(f"Loaded {len(self._models)} models from {len(self._raw_config.providers)} providers")

    @property
    def models(self) -> List[RegisteredModel]:
        """Get all registered models."""
        if not self._models:
            self.load()
        return self._models

    def get_models_by_provider(self, provider_name: str) -> List[RegisteredModel]:
        """Get all models from a specific provider."""
        return [model for model in self.models if model.provider_name == provider_name]

    def get_model_by_id(self, model_id: str) -> Optional[RegisteredModel]:
        """Get a specific model by ID."""
        for model in self.models:
            if model.model_id == model_id:
                return model
        return None

    def get_models_by_capability(self, capability: str) -> List[RegisteredModel]:
        """Get all models that have a specific capability."""
        return [model for model in self.models if capability in model.config.capabilities]

    def get_local_models(self) -> List[RegisteredModel]:
        """Get all local models."""
        return [model for model in self.models if model.provider.type == "local"]

    def get_cloud_models(self) -> List[RegisteredModel]:
        """Get all cloud models."""
        return [model for model in self.models if model.provider.type == "cloud"]
