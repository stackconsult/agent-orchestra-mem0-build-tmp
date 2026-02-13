"""
Request Telemetry

Captures detailed metrics for each model request including
latency, cost, quality, and performance indicators.
"""

import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ConfigDict


class CriticalityLevel(str, Enum):
    """Request criticality levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """Standardized task types."""
    CHAT = "chat"
    QA = "qa"
    CODING = "coding"
    REASONING = "reasoning"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    CREATIVE = "creative"
    ANALYSIS = "analysis"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"


@dataclass
class RequestTiming:
    """Detailed timing information for a request."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    model_selection_time_ms: float = 0.0
    provider_call_time_ms: float = 0.0
    response_generation_time_ms: float = 0.0
    total_latency_ms: float = 0.0
    
    def mark_end(self):
        """Mark the end of the request."""
        self.end_time = datetime.now()
        self.total_latency_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def get_breakdown(self) -> Dict[str, float]:
        """Get timing breakdown as percentages."""
        if self.total_latency_ms == 0:
            return {}
        
        return {
            "model_selection_pct": (self.model_selection_time_ms / self.total_latency_ms) * 100,
            "provider_call_pct": (self.provider_call_time_ms / self.total_latency_ms) * 100,
            "response_generation_pct": (self.response_generation_time_ms / self.total_latency_ms) * 100
        }


@dataclass
class TokenUsage:
    """Token usage information."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    context_window_used: int = 0
    context_window_total: int = 0
    
    def calculate_cost(self, input_cost_per_1k: float, output_cost_per_1k: float) -> float:
        """Calculate total cost based on token usage."""
        input_cost = (self.input_tokens / 1000) * input_cost_per_1k
        output_cost = (self.output_tokens / 1000) * output_cost_per_1k
        return input_cost + output_cost
    
    def get_context_usage_pct(self) -> float:
        """Get context usage as percentage."""
        if self.context_window_total == 0:
            return 0.0
        return (self.context_window_used / self.context_window_total) * 100


@dataclass
class QualityMetrics:
    """Quality assessment metrics."""
    overall_score: float = 0.0  # 0-1
    relevance_score: float = 0.0  # 0-1
    coherence_score: float = 0.0  # 0-1
    accuracy_score: float = 0.0  # 0-1
    completeness_score: float = 0.0  # 0-1
    
    # Task-specific scores
    task_specific_scores: Dict[str, float] = field(default_factory=dict)
    
    # Validation results
    passed_validation: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def calculate_weighted_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate weighted quality score."""
        if weights is None:
            weights = {
                "relevance": 0.3,
                "coherence": 0.25,
                "accuracy": 0.25,
                "completeness": 0.2
            }
        
        weighted_score = (
            self.relevance_score * weights.get("relevance", 0.3) +
            self.coherence_score * weights.get("coherence", 0.25) +
            self.accuracy_score * weights.get("accuracy", 0.25) +
            self.completeness_score * weights.get("completeness", 0.2)
        )
        
        return min(max(weighted_score, 0.0), 1.0)


@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    was_cached: bool = False
    cache_hit: bool = False
    cache_key: Optional[str] = None
    cache_lookup_time_ms: float = 0.0
    cache_store_time_ms: float = 0.0
    
    # Cache efficiency
    similarity_score: float = 0.0  # For semantic cache
    cache_age_seconds: float = 0.0
    
    def get_cache_efficiency_score(self) -> float:
        """Calculate cache efficiency score."""
        if not self.was_cached:
            return 0.0
        
        if self.cache_hit:
            # Higher score for direct hits
            return 0.9 + (0.1 * self.similarity_score)
        else:
            # Lower score for misses
            return 0.1


class RequestMetrics(BaseModel):
    """Complete metrics for a single request."""
    
    # Request identification
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Request metadata
    task_type: TaskType
    criticality: CriticalityLevel = CriticalityLevel.MEDIUM
    prompt_length: int = 0
    response_length: int = 0
    
    # Model selection
    selected_model_id: str
    selected_provider: str
    selection_confidence: float = 0.0  # 0-1
    selection_reason: Optional[str] = None
    
    # Timing information
    timing: RequestTiming = Field(default_factory=RequestTiming)
    
    # Token usage
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    
    # Cost information
    cost_usd: float = 0.0
    budget_impact: Optional[str] = None  # "within_budget", "approaching_limit", "exceeded"
    
    # Quality metrics
    quality: QualityMetrics = Field(default_factory=QualityMetrics)
    
    # Cache metrics
    cache: CacheMetrics = Field(default_factory=CacheMetrics)
    
    # Success/error information
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    # Performance indicators
    latency_p99_ms: Optional[float] = None  # For comparison
    cost_savings_usd: float = 0.0  # Savings from caching, local models, etc.
    
    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(use_enum_values=True)
    
    def mark_completed(self):
        """Mark the request as completed."""
        self.timing.mark_end()
        self.completed_at = datetime.now()
    
    def calculate_efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-1)."""
        # Weight factors
        speed_weight = 0.3
        cost_weight = 0.3
        quality_weight = 0.25
        cache_weight = 0.15
        
        # Normalize metrics
        speed_score = min(1000 / max(self.timing.total_latency_ms, 1), 1.0)  # Target < 1s
        cost_score = min(0.01 / max(self.cost_usd, 0.0001), 1.0)  # Target < $0.01
        quality_score = self.quality.overall_score
        cache_score = self.cache.get_cache_efficiency_score()
        
        efficiency = (
            speed_score * speed_weight +
            cost_score * cost_weight +
            quality_score * quality_weight +
            cache_score * cache_weight
        )
        
        return min(max(efficiency, 0.0), 1.0)
    
    def get_performance_tier(self) -> str:
        """Get performance tier classification."""
        efficiency = self.calculate_efficiency_score()
        
        if efficiency >= 0.9:
            return "excellent"
        elif efficiency >= 0.75:
            return "good"
        elif efficiency >= 0.6:
            return "acceptable"
        elif efficiency >= 0.4:
            return "poor"
        else:
            return "unacceptable"
    
    def to_timescale_record(self) -> Dict[str, Any]:
        """Convert to TimescaleDB record format."""
        return {
            "time": self.created_at,
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "model_id": self.selected_model_id,
            "provider": self.selected_provider,
            "task_type": self.task_type.value,
            
            "latency_ms": self.timing.total_latency_ms,
            "input_tokens": self.token_usage.input_tokens,
            "output_tokens": self.token_usage.output_tokens,
            "total_tokens": self.token_usage.total_tokens,
            "cost_usd": self.cost_usd,
            
            "was_cached": self.cache.was_cached,
            "cache_hit": self.cache.cache_hit,
            "response_valid": self.quality.passed_validation,
            "quality_score": self.quality.overall_score,
            
            "criticality": self.criticality.value,
            "success": self.success,
            "error_message": self.error_message,
            
            "ip_address": self.ip_address,
            "user_agent": self.user_agent
        }


class RequestTelemetry:
    """Manages request telemetry collection and processing."""
    
    def __init__(self):
        """Initialize telemetry collector."""
        self.active_requests: Dict[str, RequestMetrics] = {}
    
    def start_request(self, 
                     tenant_id: str,
                     task_type: TaskType,
                     criticality: CriticalityLevel = CriticalityLevel.MEDIUM,
                     user_id: Optional[str] = None,
                     session_id: Optional[str] = None,
                     prompt: Optional[str] = None,
                     **metadata) -> RequestMetrics:
        """Start tracking a new request."""
        metrics = RequestMetrics(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            criticality=criticality,
            prompt_length=len(prompt) if prompt else 0,
            request_metadata=metadata
        )
        
        self.active_requests[metrics.request_id] = metrics
        return metrics
    
    def record_model_selection(self, 
                             request_id: str,
                             model_id: str,
                             provider: str,
                             confidence: float,
                             reason: Optional[str] = None,
                             selection_time_ms: float = 0.0):
        """Record model selection for a request."""
        if request_id not in self.active_requests:
            return
        
        metrics = self.active_requests[request_id]
        metrics.selected_model_id = model_id
        metrics.selected_provider = provider
        metrics.selection_confidence = confidence
        metrics.selection_reason = reason
        metrics.timing.model_selection_time_ms = selection_time_ms
    
    def record_provider_call(self, 
                           request_id: str,
                           call_time_ms: float,
                           input_tokens: int,
                           output_tokens: int,
                           context_window_used: int,
                           context_window_total: int,
                           cost_usd: float):
        """Record provider call metrics."""
        if request_id not in self.active_requests:
            return
        
        metrics = self.active_requests[request_id]
        metrics.timing.provider_call_time_ms = call_time_ms
        metrics.token_usage.input_tokens = input_tokens
        metrics.token_usage.output_tokens = output_tokens
        metrics.token_usage.total_tokens = input_tokens + output_tokens
        metrics.token_usage.context_window_used = context_window_used
        metrics.token_usage.context_window_total = context_window_total
        metrics.cost_usd = cost_usd
    
    def record_cache_result(self,
                          request_id: str,
                          was_cached: bool,
                          cache_hit: bool,
                          cache_key: Optional[str] = None,
                          lookup_time_ms: float = 0.0,
                          similarity_score: float = 0.0):
        """Record cache performance metrics."""
        if request_id not in self.active_requests:
            return
        
        metrics = self.active_requests[request_id]
        metrics.cache.was_cached = was_cached
        metrics.cache.cache_hit = cache_hit
        metrics.cache.cache_key = cache_key
        metrics.cache.cache_lookup_time_ms = lookup_time_ms
        metrics.cache.similarity_score = similarity_score
    
    def record_quality_metrics(self,
                              request_id: str,
                              quality_score: float,
                              relevance_score: float,
                              coherence_score: float,
                              accuracy_score: float,
                              completeness_score: float,
                              passed_validation: bool = True,
                              validation_errors: Optional[List[str]] = None):
        """Record quality assessment metrics."""
        if request_id not in self.active_requests:
            return
        
        metrics = self.active_requests[request_id]
        metrics.quality.overall_score = quality_score
        metrics.quality.relevance_score = relevance_score
        metrics.quality.coherence_score = coherence_score
        metrics.quality.accuracy_score = accuracy_score
        metrics.quality.completeness_score = completeness_score
        metrics.quality.passed_validation = passed_validation
        metrics.quality.validation_errors = validation_errors or []
    
    def record_response(self,
                       request_id: str,
                       response: str,
                       response_generation_time_ms: float,
                       success: bool = True,
                       error_code: Optional[str] = None,
                       error_message: Optional[str] = None):
        """Record response information and complete the request."""
        if request_id not in self.active_requests:
            return
        
        metrics = self.active_requests[request_id]
        metrics.response_length = len(response)
        metrics.timing.response_generation_time_ms = response_generation_time_ms
        metrics.success = success
        metrics.error_code = error_code
        metrics.error_message = error_message
        
        # Mark as completed
        metrics.mark_completed()
    
    def complete_request(self, request_id: str) -> Optional[RequestMetrics]:
        """Complete request tracking and return metrics."""
        if request_id not in self.active_requests:
            return None
        
        metrics = self.active_requests[request_id]
        metrics.mark_completed()
        
        # Remove from active requests
        del self.active_requests[request_id]
        
        return metrics
    
    def get_active_request_count(self) -> int:
        """Get number of currently active requests."""
        return len(self.active_requests)
    
    def get_active_requests_by_tenant(self, tenant_id: str) -> List[RequestMetrics]:
        """Get active requests for a specific tenant."""
        return [
            metrics for metrics in self.active_requests.values()
            if metrics.tenant_id == tenant_id
        ]
