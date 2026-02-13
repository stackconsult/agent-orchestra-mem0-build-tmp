"""
Discovery Orchestrator

Coordinates parallel model discovery across providers and manages
the model registry with auto-discovery capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass

from .model_inspector import ModelInspector, ProviderConfig
from .model_profile import ModelProfile


logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Configuration for model discovery."""
    enabled: bool = True
    schedule: str = "0 0 * * *"  # Daily at midnight
    parallel_discovery: bool = True
    max_concurrent_providers: int = 5
    benchmark_sample_size: int = 3  # Number of models to benchmark per provider
    auto_benchmark_new_models: bool = True
    retry_failed_discoveries: bool = True
    max_retry_attempts: int = 3


class DiscoveryOrchestrator:
    """Orchestrates model discovery across providers."""
    
    def __init__(self, config: DiscoveryConfig):
        """Initialize discovery orchestrator."""
        self.config = config
        self.inspector = ModelInspector()
        self.provider_configs: List[ProviderConfig] = []
        self.discovered_models: Dict[str, ModelProfile] = {}
        self.failed_providers: Set[str] = set()
        self.last_discovery: Optional[datetime] = None
        self.discovery_in_progress = False
    
    async def auto_discover_all(self, provider_configs: List[ProviderConfig]) -> Dict[str, ModelProfile]:
        """Perform automatic discovery across all providers."""
        if not self.config.enabled:
            logger.info("Auto-discovery is disabled")
            return {}
        
        if self.discovery_in_progress:
            logger.warning("Discovery already in progress, skipping")
            return self.discovered_models
        
        self.discovery_in_progress = True
        self.provider_configs = provider_configs
        
        try:
            logger.info(f"Starting auto-discovery for {len(provider_configs)} providers")
            
            async with self.inspector:
                if self.config.parallel_discovery:
                    await self._parallel_discovery()
                else:
                    await self._sequential_discovery()
            
            self.last_discovery = datetime.now()
            logger.info(f"Discovery completed. Found {len(self.discovered_models)} models")
            
            return self.discovered_models
            
        except Exception as e:
            logger.error(f"Auto-discovery failed: {e}")
            return self.discovered_models
        finally:
            self.discovery_in_progress = False
    
    async def _parallel_discovery(self) -> None:
        """Perform parallel discovery across providers."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent_providers)
        
        async def discover_with_semaphore(config: ProviderConfig) -> List[ModelProfile]:
            async with semaphore:
                return await self._discover_provider_safe(config)
        
        tasks = [discover_with_semaphore(config) for config in self.provider_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            provider_name = self.provider_configs[i].name
            if isinstance(result, Exception):
                logger.error(f"Provider {provider_name} failed: {result}")
                self.failed_providers.add(provider_name)
            elif isinstance(result, list):
                logger.info(f"Provider {provider_name} discovered {len(result)} models")
                for profile in result:
                    self.discovered_models[f"{profile.provider}:{profile.model_id}"] = profile
    
    async def _sequential_discovery(self) -> None:
        """Perform sequential discovery across providers."""
        for config in self.provider_configs:
            try:
                profiles = await self._discover_provider_safe(config)
                logger.info(f"Provider {config.name} discovered {len(profiles)} models")
                for profile in profiles:
                    self.discovered_models[f"{profile.provider}:{profile.model_id}"] = profile
            except Exception as e:
                logger.error(f"Provider {config.name} failed: {e}")
                self.failed_providers.add(config.name)
    
    async def _discover_provider_safe(self, config: ProviderConfig) -> List[ModelProfile]:
        """Safely discover models from a provider with retries."""
        last_error = None
        
        for attempt in range(self.config.max_retry_attempts):
            try:
                profiles = await self.inspector._discover_provider_models(config)
                
                # Remove from failed providers if successful
                self.failed_providers.discard(config.name)
                
                # Run benchmarks on sample of new models
                if self.config.auto_benchmark_new_models and profiles:
                    await self._benchmark_sample_models(profiles)
                
                return profiles
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {config.name} attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        # All attempts failed
        self.failed_providers.add(config.name)
        raise last_error or Exception("Discovery failed after all retries")
    
    async def _benchmark_sample_models(self, profiles: List[ModelProfile]) -> None:
        """Benchmark a sample of newly discovered models."""
        # Select sample models for benchmarking
        sample_size = min(self.config.benchmark_sample_size, len(profiles))
        sample_profiles = profiles[:sample_size]
        
        logger.info(f"Benchmarking {len(sample_profiles)} sample models")
        
        # Note: Actual benchmarking would require model clients
        # For now, we'll just log that we would benchmark
        for profile in sample_profiles:
            logger.info(f"Would benchmark model: {profile.provider}:{profile.model_id}")
            # TODO: Implement actual benchmarking with model clients
    
    async def discover_provider(self, provider_name: str) -> List[ModelProfile]:
        """Discover models from a specific provider."""
        config = next((c for c in self.provider_configs if c.name == provider_name), None)
        if not config:
            raise ValueError(f"Provider {provider_name} not configured")
        
        async with self.inspector:
            profiles = await self._discover_provider_safe(config)
            
            # Update discovered models
            for profile in profiles:
                key = f"{profile.provider}:{profile.model_id}"
                self.discovered_models[key] = profile
            
            return profiles
    
    def get_discovered_models(self) -> Dict[str, ModelProfile]:
        """Get all discovered models."""
        return self.discovered_models.copy()
    
    def get_models_by_provider(self, provider: str) -> List[ModelProfile]:
        """Get models from a specific provider."""
        return [
            profile for profile in self.discovered_models.values()
            if profile.provider == provider
        ]
    
    def get_models_by_quality_tier(self, tier: str) -> List[ModelProfile]:
        """Get models by quality tier."""
        return [
            profile for profile in self.discovered_models.values()
            if profile.quality_tier.value == tier
        ]
    
    def get_models_by_capability(self, capability: str) -> List[ModelProfile]:
        """Get models that have a specific capability."""
        capable_models = []
        
        for profile in self.discovered_models.values():
            if hasattr(profile.capabilities, capability):
                if getattr(profile.capabilities, capability):
                    capable_models.append(profile)
        
        return capable_models
    
    def search_models(self, query: str) -> List[ModelProfile]:
        """Search models by name or description."""
        query_lower = query.lower()
        matching_models = []
        
        for profile in self.discovered_models.values():
            # Search in model ID, display name, and provider
            if (query_lower in profile.model_id.lower() or
                (profile.display_name and query_lower in profile.display_name.lower()) or
                query_lower in profile.provider.lower()):
                matching_models.append(profile)
        
        return matching_models
    
    def get_discovery_status(self) -> Dict[str, Any]:
        """Get current discovery status."""
        return {
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "discovery_in_progress": self.discovery_in_progress,
            "total_models_discovered": len(self.discovered_models),
            "configured_providers": len(self.provider_configs),
            "failed_providers": list(self.failed_providers),
            "models_by_provider": {
                provider: len(self.get_models_by_provider(provider))
                for provider in set(profile.provider for profile in self.discovered_models.values())
            },
            "models_by_quality_tier": {
                tier: len(self.get_models_by_quality_tier(tier))
                for tier in set(profile.quality_tier.value for profile in self.discovered_models.values())
            }
        }
    
    def is_discovery_needed(self) -> bool:
        """Check if a new discovery is needed."""
        if not self.config.enabled:
            return False
        
        if self.last_discovery is None:
            return True
        
        # Check if it's been more than 24 hours since last discovery
        time_since_discovery = datetime.now() - self.last_discovery
        return time_since_discovery > timedelta(hours=24)
    
    async def force_rediscovery(self) -> Dict[str, ModelProfile]:
        """Force a complete rediscovery of all models."""
        logger.info("Forcing complete rediscovery")
        
        # Clear existing data
        self.discovered_models.clear()
        self.failed_providers.clear()
        self.last_discovery = None
        
        # Run discovery again
        return await self.auto_discover_all(self.provider_configs)
    
    def export_model_registry(self) -> Dict[str, Any]:
        """Export model registry in YAML-compatible format."""
        registry = {
            "version": "2.0",
            "discovered_at": self.last_discovery.isoformat() if self.last_discovery else None,
            "providers": {}
        }
        
        for profile in self.discovered_models.values():
            if profile.provider not in registry["providers"]:
                registry["providers"][profile.provider] = {
                    "type": profile.provider,
                    "models": {}
                }
            
            model_data = {
                "display_name": profile.display_name,
                "context_window": profile.context_window,
                "estimated_cost_input_per_1k": profile.estimated_cost_input_per_1k,
                "estimated_cost_output_per_1k": profile.estimated_cost_output_per_1k,
                "quality_tier": profile.quality_tier.value,
                "capabilities": profile.capabilities.dict(),
                "discovered_at": profile.discovered_at.isoformat(),
                "provider_metadata": profile.provider_metadata
            }
            
            registry["providers"][profile.provider]["models"][profile.model_id] = model_data
        
        return registry
    
    def get_model_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about discovered models."""
        if not self.discovered_models:
            return {"total_models": 0}
        
        # Calculate statistics
        total_models = len(self.discovered_models)
        models_by_provider = {}
        models_by_tier = {}
        avg_context_window = 0
        avg_cost_input = 0
        avg_cost_output = 0
        
        for profile in self.discovered_models.values():
            # Provider stats
            provider = profile.provider
            models_by_provider[provider] = models_by_provider.get(provider, 0) + 1
            
            # Tier stats
            tier = profile.quality_tier.value
            models_by_tier[tier] = models_by_tier.get(tier, 0) + 1
            
            # Average stats
            avg_context_window += profile.context_window
            avg_cost_input += profile.estimated_cost_input_per_1k
            avg_cost_output += profile.estimated_cost_output_per_1k
        
        avg_context_window /= total_models
        avg_cost_input /= total_models
        avg_cost_output /= total_models
        
        return {
            "total_models": total_models,
            "models_by_provider": models_by_provider,
            "models_by_quality_tier": models_by_tier,
            "average_context_window": round(avg_context_window),
            "average_cost_per_1k_tokens": {
                "input": round(avg_cost_input, 6),
                "output": round(avg_cost_output, 6)
            },
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "failed_providers": list(self.failed_providers)
        }
