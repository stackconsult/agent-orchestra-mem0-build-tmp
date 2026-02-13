"""
Model Profile Schema

Defines the data structure for storing model information,
capabilities, and benchmark results.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class QualityTier(str, Enum):
    """Model quality classification."""
    BASIC = "basic"
    STANDARD = "standard" 
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ModelCapabilities(BaseModel):
    """Model capability flags."""
    supports_chat: bool = False
    supports_completion: bool = False
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_code_generation: bool = False
    supports_reasoning: bool = False
    supports_multimodal: bool = False
    supports_streaming: bool = False
    supports_json_mode: bool = False
    supports_system_prompt: bool = False
    
    # Task-specific capabilities
    qa_accuracy: Optional[float] = None  # 0-1 score
    coding_ability: Optional[float] = None  # 0-1 score
    reasoning_depth: Optional[float] = None  # 0-1 score
    creativity: Optional[float] = None  # 0-1 score
    speed: Optional[float] = None  # tokens/second


class BenchmarkResult(BaseModel):
    """Individual benchmark test result."""
    test_name: str
    prompt: str
    expected_response: Optional[str] = None
    actual_response: str
    latency_ms: float
    tokens_per_second: float
    quality_score: float  # 0-1
    cost_per_1k_tokens: float
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ModelProfile(BaseModel):
    """Complete model profile with metadata and benchmarks."""
    provider: str
    model_id: str
    display_name: Optional[str] = None
    
    # Basic metadata
    context_window: int
    max_output_tokens: Optional[int] = None
    estimated_cost_input_per_1k: float
    estimated_cost_output_per_1k: float
    
    # Capabilities assessment
    capabilities: ModelCapabilities
    
    # Quality classification
    quality_tier: QualityTier
    
    # Benchmark results
    benchmark_results: List[BenchmarkResult] = []
    average_quality_score: float = 0.0
    average_latency_ms: float = 0.0
    average_tokens_per_second: float = 0.0
    
    # Discovery metadata
    discovered_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    last_tested: Optional[datetime] = None
    
    # Provider-specific metadata
    provider_metadata: Dict[str, Any] = {}
    
    # Health and availability
    is_available: bool = True
    last_health_check: Optional[datetime] = None
    health_check_failures: int = 0
    
    model_config = ConfigDict(use_enum_values=True)
        
    def update_benchmarks(self, new_results: List[BenchmarkResult]) -> None:
        """Update benchmark results and recalculate averages."""
        self.benchmark_results.extend(new_results)
        self.last_tested = datetime.now()
        self._recalculate_averages()
        self.last_updated = datetime.now()
    
    def _recalculate_averages(self) -> None:
        """Recalculate average metrics from benchmark results."""
        if not self.benchmark_results:
            return
            
        successful_results = [r for r in self.benchmark_results if r.success]
        if not successful_results:
            return
            
        self.average_quality_score = sum(r.quality_score for r in successful_results) / len(successful_results)
        self.average_latency_ms = sum(r.latency_ms for r in successful_results) / len(successful_results)
        self.average_tokens_per_second = sum(r.tokens_per_second for r in successful_results) / len(successful_results)
    
    def get_efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-1)."""
        # Weight factors
        quality_weight = 0.4
        speed_weight = 0.3
        cost_weight = 0.3
        
        # Normalize metrics
        quality_score = self.average_quality_score
        speed_score = min(self.average_tokens_per_second / 100, 1.0)  # Normalize to 100 t/s
        cost_score = max(0, 1 - (self.estimated_cost_input_per_1k / 0.01))  # Normalize to $0.01 per 1k
        
        efficiency = (quality_score * quality_weight + 
                     speed_score * speed_weight + 
                     cost_score * cost_weight)
        
        return min(max(efficiency, 0), 1)
    
    def is_suitable_for_task(self, task_type: str, requirements: Dict[str, Any]) -> bool:
        """Check if model is suitable for specific task requirements."""
        # Basic capability checks
        if task_type == "coding" and not self.capabilities.supports_code_generation:
            return False
        if task_type == "qa" and (self.capabilities.qa_accuracy or 0) < requirements.get("min_accuracy", 0.7):
            return False
        if task_type == "reasoning" and (self.capabilities.reasoning_depth or 0) < requirements.get("min_reasoning", 0.7):
            return False
            
        # Context window check
        required_context = requirements.get("max_context", 4096)
        if self.context_window < required_context:
            return False
            
        # Quality tier check
        min_tier = requirements.get("min_quality_tier", QualityTier.BASIC)
        tier_hierarchy = {
            QualityTier.BASIC: 0,
            QualityTier.STANDARD: 1,
            QualityTier.PREMIUM: 2,
            QualityTier.ENTERPRISE: 3
        }
        if tier_hierarchy.get(self.quality_tier, 0) < tier_hierarchy.get(min_tier, 0):
            return False
            
        return True
