"""
Model Inspector

Discovers and profiles models from various providers.
Supports Ollama, OpenAI, Anthropic, and other providers.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .model_profile import ModelProfile, ModelCapabilities, QualityTier
from .benchmarks import BenchmarkSuite


logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Provider connection configuration."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3


class ModelInspector:
    """Discovers and profiles models from various providers."""
    
    def __init__(self):
        """Initialize model inspector."""
        self.benchmark_suite = BenchmarkSuite()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def discover_all_providers(self, provider_configs: List[ProviderConfig]) -> List[ModelProfile]:
        """Discover models from all configured providers in parallel."""
        tasks = []
        for config in provider_configs:
            task = asyncio.create_task(self._discover_provider_models(config))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_profiles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Provider discovery failed: {result}")
            elif isinstance(result, list):
                all_profiles.extend(result)
        
        return all_profiles
    
    async def _discover_provider_models(self, config: ProviderConfig) -> List[ModelProfile]:
        """Discover models from a specific provider."""
        try:
            if config.name.lower() == "ollama":
                return await self._introspect_ollama(config)
            elif config.name.lower() == "openai":
                return await self._introspect_openai(config)
            elif config.name.lower() == "anthropic":
                return await self._introspect_anthropic(config)
            elif config.name.lower() == "deepseek":
                return await self._introspect_deepseek(config)
            else:
                logger.warning(f"Unsupported provider: {config.name}")
                return []
        except Exception as e:
            logger.error(f"Failed to discover models for provider {config.name}: {e}")
            return []
    
    async def _introspect_ollama(self, config: ProviderConfig) -> List[ModelProfile]:
        """Introspect Ollama models."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        try:
            # Get list of available models
            async with self.session.get(f"{config.base_url}/api/tags", timeout=config.timeout) as response:
                if response.status != 200:
                    logger.error(f"Ollama API returned status {response.status}")
                    return []
                
                data = await response.json()
                models = data.get("models", [])
            
            profiles = []
            for model_info in models:
                try:
                    profile = await self._create_ollama_profile(config, model_info)
                    if profile:
                        profiles.append(profile)
                except Exception as e:
                    logger.error(f"Failed to create profile for Ollama model {model_info.get('name')}: {e}")
            
            return profiles
            
        except Exception as e:
            logger.error(f"Ollama introspection failed: {e}")
            return []
    
    async def _create_ollama_profile(self, config: ProviderConfig, model_info: Dict[str, Any]) -> Optional[ModelProfile]:
        """Create model profile for Ollama model."""
        model_name = model_info["name"]
        size = model_info.get("size", 0)  # Size in bytes
        digest = model_info.get("digest", "")
        
        # Estimate model capabilities based on name
        capabilities = self._infer_ollama_capabilities(model_name)
        
        # Estimate context window and costs
        context_window, cost_input, cost_output = self._estimate_ollama_specs(model_name, size)
        
        # Determine quality tier
        quality_tier = self._determine_ollama_quality_tier(model_name, size)
        
        profile = ModelProfile(
            provider="ollama",
            model_id=model_name,
            display_name=self._format_display_name(model_name),
            context_window=context_window,
            estimated_cost_input_per_1k=cost_input,
            estimated_cost_output_per_1k=cost_output,
            capabilities=capabilities,
            quality_tier=quality_tier,
            provider_metadata={
                "size": size,
                "digest": digest,
                "modified_at": model_info.get("modified_at"),
                "base_url": config.base_url
            }
        )
        
        return profile
    
    def _infer_ollama_capabilities(self, model_name: str) -> ModelCapabilities:
        """Infer model capabilities from name."""
        capabilities = ModelCapabilities()
        
        name_lower = model_name.lower()
        
        # Basic capabilities most models have
        capabilities.supports_chat = True
        capabilities.supports_completion = True
        capabilities.supports_system_prompt = True
        capabilities.supports_streaming = True
        
        # Advanced capabilities
        if "instruct" in name_lower or "chat" in name_lower:
            capabilities.supports_chat = True
            capabilities.qa_accuracy = 0.8
        
        if "code" in name_lower or "coder" in name_lower:
            capabilities.supports_code_generation = True
            capabilities.coding_ability = 0.7
        
        if any(size in name_lower for size in ["70b", "65b", "405b"]):
            capabilities.supports_reasoning = True
            capabilities.reasoning_depth = 0.8
            capabilities.qa_accuracy = 0.9
        
        if "vision" in name_lower or "multimodal" in name_lower:
            capabilities.supports_vision = True
            capabilities.supports_multimodal = True
        
        if "tool" in name_lower or "function" in name_lower:
            capabilities.supports_function_calling = True
            capabilities.supports_json_mode = True
        
        # Set quality scores based on model size and type
        if any(size in name_lower for size in ["405b", "70b", "65b"]):
            capabilities.qa_accuracy = 0.9
            capabilities.reasoning_depth = 0.9
            capabilities.creativity = 0.8
        elif any(size in name_lower for size in ["34b", "33b", "30b", "13b", "12b"]):
            capabilities.qa_accuracy = 0.8
            capabilities.reasoning_depth = 0.7
            capabilities.creativity = 0.7
        else:
            capabilities.qa_accuracy = 0.7
            capabilities.reasoning_depth = 0.6
            capabilities.creativity = 0.6
        
        return capabilities
    
    def _estimate_ollama_specs(self, model_name: str, size_bytes: int) -> Tuple[int, float, float]:
        """Estimate context window and costs for Ollama model."""
        name_lower = model_name.lower()
        
        # Context window estimation
        if "405b" in name_lower:
            context_window = 128000
        elif any(size in name_lower for size in ["70b", "65b"]):
            context_window = 32768
        elif any(size in name_lower for size in ["34b", "33b", "30b"]):
            context_window = 8192
        elif any(size in name_lower for size in ["13b", "12b", "8b"]):
            context_window = 4096
        else:
            context_window = 2048
        
        # Cost estimation (Ollama is free, but we estimate compute cost)
        # Based on model size and typical cloud pricing
        size_gb = size_bytes / (1024**3) if size_bytes > 0 else 1
        
        if "405b" in name_lower:
            cost_input = 0.003  # $0.003 per 1k tokens (equivalent)
            cost_output = 0.003
        elif any(size in name_lower for size in ["70b", "65b"]):
            cost_input = 0.001
            cost_output = 0.001
        elif any(size in name_lower for size in ["34b", "33b", "30b"]):
            cost_input = 0.0005
            cost_output = 0.0005
        else:
            cost_input = 0.0001  # Essentially free
            cost_output = 0.0001
        
        return context_window, cost_input, cost_output
    
    def _determine_ollama_quality_tier(self, model_name: str, size_bytes: int) -> QualityTier:
        """Determine quality tier for Ollama model."""
        name_lower = model_name.lower()
        
        if "405b" in name_lower:
            return QualityTier.ENTERPRISE
        elif any(size in name_lower for size in ["70b", "65b"]):
            return QualityTier.PREMIUM
        elif any(size in name_lower for size in ["34b", "33b", "30b", "13b", "12b"]):
            return QualityTier.STANDARD
        else:
            return QualityTier.BASIC
    
    def _format_display_name(self, model_name: str) -> str:
        """Format model name for display."""
        # Convert to title case and replace common abbreviations
        name = model_name.replace("-", " ").replace("_", " ").title()
        name = name.replace("Llma", "LLaMA").replace("Gpt", "GPT").replace("Qwen", "Qwen")
        return name
    
    async def _introspect_openai(self, config: ProviderConfig) -> List[ModelProfile]:
        """Introspect OpenAI models."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        headers = {"Authorization": f"Bearer {config.api_key}"}
        
        try:
            async with self.session.get(f"{config.base_url}/models", headers=headers, timeout=config.timeout) as response:
                if response.status != 200:
                    logger.error(f"OpenAI API returned status {response.status}")
                    return []
                
                data = await response.json()
                models = data.get("data", [])
            
            profiles = []
            for model_info in models:
                try:
                    profile = self._create_openai_profile(config, model_info)
                    if profile:
                        profiles.append(profile)
                except Exception as e:
                    logger.error(f"Failed to create profile for OpenAI model {model_info.get('id')}: {e}")
            
            return profiles
            
        except Exception as e:
            logger.error(f"OpenAI introspection failed: {e}")
            return []
    
    def _create_openai_profile(self, config: ProviderConfig, model_info: Dict[str, Any]) -> Optional[ModelProfile]:
        """Create model profile for OpenAI model."""
        model_id = model_info["id"]
        owned_by = model_info.get("owned_by", "")
        
        # Skip fine-tuned models for now
        if "ft:" in model_id or owned_by == "user":
            return None
        
        capabilities = self._infer_openai_capabilities(model_id)
        context_window, cost_input, cost_output = self._get_openai_specs(model_id)
        quality_tier = self._determine_openai_quality_tier(model_id)
        
        profile = ModelProfile(
            provider="openai",
            model_id=model_id,
            display_name=self._format_openai_display_name(model_id),
            context_window=context_window,
            estimated_cost_input_per_1k=cost_input,
            estimated_cost_output_per_1k=cost_output,
            capabilities=capabilities,
            quality_tier=quality_tier,
            provider_metadata={
                "owned_by": owned_by,
                "created_at": model_info.get("created"),
                "base_url": config.base_url
            }
        )
        
        return profile
    
    def _infer_openai_capabilities(self, model_id: str) -> ModelCapabilities:
        """Infer capabilities for OpenAI model."""
        capabilities = ModelCapabilities()
        
        # All OpenAI models support basic features
        capabilities.supports_chat = True
        capabilities.supports_completion = True
        capabilities.supports_system_prompt = True
        capabilities.supports_streaming = True
        capabilities.supports_function_calling = True
        capabilities.supports_json_mode = True
        
        if "gpt-4" in model_id:
            capabilities.supports_reasoning = True
            capabilities.supports_code_generation = True
            capabilities.qa_accuracy = 0.95
            capabilities.reasoning_depth = 0.9
            capabilities.coding_ability = 0.85
            capabilities.creativity = 0.9
        
        if "gpt-3.5" in model_id:
            capabilities.qa_accuracy = 0.8
            capabilities.reasoning_depth = 0.7
            capabilities.coding_ability = 0.7
            capabilities.creativity = 0.7
        
        if "vision" in model_id:
            capabilities.supports_vision = True
            capabilities.supports_multimodal = True
        
        return capabilities
    
    def _get_openai_specs(self, model_id: str) -> Tuple[int, float, float]:
        """Get specifications for OpenAI model."""
        # Official OpenAI pricing and specs
        if "gpt-4-turbo" in model_id or "gpt-4-1106" in model_id:
            return 128000, 0.01, 0.03
        elif "gpt-4" in model_id:
            return 8192, 0.03, 0.06
        elif "gpt-3.5-turbo" in model_id:
            return 16385, 0.0015, 0.002
        else:
            # Default specs
            return 4096, 0.002, 0.002
    
    def _determine_openai_quality_tier(self, model_id: str) -> QualityTier:
        """Determine quality tier for OpenAI model."""
        if "gpt-4" in model_id:
            return QualityTier.ENTERPRISE if "turbo" in model_id else QualityTier.PREMIUM
        elif "gpt-3.5" in model_id:
            return QualityTier.STANDARD
        else:
            return QualityTier.BASIC
    
    def _format_openai_display_name(self, model_id: str) -> str:
        """Format OpenAI model name for display."""
        return model_id.replace("-", " ").title()
    
    async def _introspect_anthropic(self, config: ProviderConfig) -> List[ModelProfile]:
        """Introspect Anthropic models (static list for now)."""
        # Anthropic doesn't have a public models API, so we use static list
        anthropic_models = [
            {
                "id": "claude-3-5-sonnet-20241022",
                "display_name": "Claude 3.5 Sonnet",
                "context_window": 200000,
                "cost_input": 0.003,
                "cost_output": 0.015
            },
            {
                "id": "claude-3-opus-20240229",
                "display_name": "Claude 3 Opus",
                "context_window": 200000,
                "cost_input": 0.015,
                "cost_output": 0.075
            },
            {
                "id": "claude-3-sonnet-20240229",
                "display_name": "Claude 3 Sonnet",
                "context_window": 200000,
                "cost_input": 0.003,
                "cost_output": 0.015
            },
            {
                "id": "claude-3-haiku-20240307",
                "display_name": "Claude 3 Haiku",
                "context_window": 200000,
                "cost_input": 0.00025,
                "cost_output": 0.00125
            }
        ]
        
        profiles = []
        for model_info in anthropic_models:
            capabilities = self._infer_anthropic_capabilities(model_info["id"])
            quality_tier = self._determine_anthropic_quality_tier(model_info["id"])
            
            profile = ModelProfile(
                provider="anthropic",
                model_id=model_info["id"],
                display_name=model_info["display_name"],
                context_window=model_info["context_window"],
                estimated_cost_input_per_1k=model_info["cost_input"],
                estimated_cost_output_per_1k=model_info["cost_output"],
                capabilities=capabilities,
                quality_tier=quality_tier,
                provider_metadata={
                    "base_url": config.base_url
                }
            )
            profiles.append(profile)
        
        return profiles
    
    def _infer_anthropic_capabilities(self, model_id: str) -> ModelCapabilities:
        """Infer capabilities for Anthropic model."""
        capabilities = ModelCapabilities()
        
        # All Claude models support these
        capabilities.supports_chat = True
        capabilities.supports_completion = True
        capabilities.supports_system_prompt = True
        capabilities.supports_streaming = True
        capabilities.supports_reasoning = True
        capabilities.qa_accuracy = 0.9
        capabilities.reasoning_depth = 0.85
        capabilities.creativity = 0.8
        
        if "opus" in model_id:
            capabilities.qa_accuracy = 0.95
            capabilities.reasoning_depth = 0.95
            capabilities.coding_ability = 0.9
            capabilities.creativity = 0.9
        elif "sonnet" in model_id:
            capabilities.coding_ability = 0.85
            capabilities.creativity = 0.85
        elif "haiku" in model_id:
            capabilities.coding_ability = 0.7
            capabilities.creativity = 0.7
        
        return capabilities
    
    def _determine_anthropic_quality_tier(self, model_id: str) -> QualityTier:
        """Determine quality tier for Anthropic model."""
        if "opus" in model_id:
            return QualityTier.ENTERPRISE
        elif "sonnet" in model_id:
            return QualityTier.PREMIUM
        elif "haiku" in model_id:
            return QualityTier.STANDARD
        else:
            return QualityTier.BASIC
    
    async def _introspect_deepseek(self, config: ProviderConfig) -> List[ModelProfile]:
        """Introspect DeepSeek models (static list for now)."""
        # DeepSeek models - static list as they don't have public API for model listing
        deepseek_models = [
            {
                "id": "deepseek-coder",
                "display_name": "DeepSeek Coder",
                "context_window": 4096,
                "cost_input": 0.00014,
                "cost_output": 0.00028
            },
            {
                "id": "deepseek-chat",
                "display_name": "DeepSeek Chat",
                "context_window": 4096,
                "cost_input": 0.00014,
                "cost_output": 0.00028
            }
        ]
        
        profiles = []
        for model_info in deepseek_models:
            capabilities = self._infer_deepseek_capabilities(model_info["id"])
            quality_tier = QualityTier.STANDARD  # DeepSeek models are standard quality
            
            profile = ModelProfile(
                provider="deepseek",
                model_id=model_info["id"],
                display_name=model_info["display_name"],
                context_window=model_info["context_window"],
                estimated_cost_input_per_1k=model_info["cost_input"],
                estimated_cost_output_per_1k=model_info["cost_output"],
                capabilities=capabilities,
                quality_tier=quality_tier,
                provider_metadata={
                    "base_url": config.base_url
                }
            )
            profiles.append(profile)
        
        return profiles
    
    def _infer_deepseek_capabilities(self, model_id: str) -> ModelCapabilities:
        """Infer capabilities for DeepSeek model."""
        capabilities = ModelCapabilities()
        
        capabilities.supports_chat = True
        capabilities.supports_completion = True
        capabilities.supports_system_prompt = True
        capabilities.supports_streaming = True
        capabilities.qa_accuracy = 0.8
        capabilities.reasoning_depth = 0.7
        capabilities.creativity = 0.6
        
        if "coder" in model_id:
            capabilities.supports_code_generation = True
            capabilities.coding_ability = 0.9
        
        return capabilities
