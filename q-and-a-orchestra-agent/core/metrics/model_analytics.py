"""
Model Analytics

Provides analytics and insights on model performance,
usage patterns, and optimization opportunities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .telemetry_store import TelemetryStore


logger = logging.getLogger(__name__)


class PerformanceTier(str, Enum):
    """Model performance tiers."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNACCEPTABLE = "unacceptable"


@dataclass
class ModelPerformanceSummary:
    """Performance summary for a model."""
    model_id: str
    provider: str
    request_count: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_quality_score: float
    avg_cost_usd: float
    success_rate: float
    cache_hit_rate: float
    efficiency_score: float
    performance_tier: PerformanceTier
    
    # Task-specific performance
    task_performance: Dict[str, Dict[str, float]]
    
    # Trends
    latency_trend: str  # "improving", "stable", "degrading"
    quality_trend: str
    cost_trend: str
    
    # Recommendations
    recommendations: List[str]


@dataclass
class CostOptimization:
    """Cost optimization opportunity."""
    type: str  # "cache", "local_model", "model_downgrade", "batch_requests"
    description: str
    potential_savings_usd: float
    implementation_effort: str  # "low", "medium", "high"
    impact_score: float  # 0-1


@dataclass
class UsageAnomaly:
    """Usage anomaly detection."""
    timestamp: datetime
    anomaly_type: str  # "spike", "drop", "error_increase", "latency_spike"
    description: str
    severity: str  # "low", "medium", "high", "critical"
    affected_models: List[str]
    metrics: Dict[str, float]


class ModelAnalytics:
    """Analytics engine for model performance and usage."""
    
    def __init__(self, telemetry_store: TelemetryStore):
        """Initialize analytics engine."""
        self.telemetry_store = telemetry_store
    
    async def get_model_performance_summary(self,
                                          model_id: str,
                                          time_range: timedelta = timedelta(days=7)) -> ModelPerformanceSummary:
        """Get comprehensive performance summary for a model."""
        # Get base performance metrics
        performance = await self.telemetry_store.get_model_performance(model_id, time_range)
        
        if not performance:
            raise ValueError(f"No performance data found for model {model_id}")
        
        # Calculate performance tier
        efficiency_score = self._calculate_efficiency_score(performance)
        performance_tier = self._determine_performance_tier(efficiency_score)
        
        # Get task-specific performance
        task_performance = await self._get_task_performance(model_id, time_range)
        
        # Analyze trends
        latency_trend = await self._analyze_latency_trend(model_id, time_range)
        quality_trend = await self._analyze_quality_trend(model_id, time_range)
        cost_trend = await self._analyze_cost_trend(model_id, time_range)
        
        # Generate recommendations
        recommendations = await self._generate_model_recommendations(
            model_id, performance, task_performance, time_range
        )
        
        return ModelPerformanceSummary(
            model_id=model_id,
            provider=performance.get("provider", "unknown"),
            request_count=performance.get("request_count", 0),
            avg_latency_ms=performance.get("avg_latency", 0),
            p95_latency_ms=performance.get("p95_latency", 0),
            p99_latency_ms=performance.get("p99_latency", 0),
            avg_quality_score=performance.get("avg_quality", 0),
            avg_cost_usd=performance.get("avg_cost", 0),
            success_rate=performance.get("success_rate", 0),
            cache_hit_rate=performance.get("cache_hit_rate", 0),
            efficiency_score=efficiency_score,
            performance_tier=performance_tier,
            task_performance=task_performance,
            latency_trend=latency_trend,
            quality_trend=quality_trend,
            cost_trend=cost_trend,
            recommendations=recommendations
        )
    
    async def compare_models(self,
                           model_ids: List[str],
                           task_type: Optional[str] = None,
                           time_range: timedelta = timedelta(days=7)) -> Dict[str, ModelPerformanceSummary]:
        """Compare performance across multiple models."""
        comparisons = {}
        
        tasks = []
        for model_id in model_ids:
            task = asyncio.create_task(
                self.get_model_performance_summary(model_id, time_range)
            )
            tasks.append((model_id, task))
        
        for model_id, task in tasks:
            try:
                summary = await task
                comparisons[model_id] = summary
            except Exception as e:
                logger.error(f"Failed to get performance summary for {model_id}: {e}")
        
        return comparisons
    
    async def get_best_models_for_task(self,
                                     task_type: str,
                                     limit: int = 5,
                                     time_range: timedelta = timedelta(days=7)) -> List[ModelPerformanceSummary]:
        """Get best performing models for a specific task."""
        task_performance = await self.telemetry_store.get_task_type_performance(
            task_type, time_range
        )
        
        # Sort by efficiency score
        sorted_models = sorted(
            task_performance,
            key=lambda x: x.get("avg_efficiency", 0),
            reverse=True
        )
        
        best_models = []
        for model_data in sorted_models[:limit]:
            model_id = model_data["model_id"]
            try:
                summary = await self.get_model_performance_summary(model_id, time_range)
                best_models.append(summary)
            except Exception as e:
                logger.error(f"Failed to get summary for {model_id}: {e}")
        
        return best_models
    
    async def identify_cost_optimization_opportunities(self,
                                                    tenant_id: Optional[str] = None,
                                                    time_range: timedelta = timedelta(days=30)) -> List[CostOptimization]:
        """Identify opportunities for cost optimization."""
        opportunities = []
        
        # Analyze cache hit rates
        cache_opportunities = await self._analyze_cache_optimization(tenant_id, time_range)
        opportunities.extend(cache_opportunities)
        
        # Analyze local model usage
        local_opportunities = await self._analyze_local_model_opportunities(tenant_id, time_range)
        opportunities.extend(local_opportunities)
        
        # Analyze model downgrades
        downgrade_opportunities = await self._analyze_model_downgrade_opportunities(tenant_id, time_range)
        opportunities.extend(downgrade_opportunities)
        
        # Sort by potential savings
        opportunities.sort(key=lambda x: x.potential_savings_usd, reverse=True)
        
        return opportunities
    
    async def detect_usage_anomalies(self,
                                   time_range: timedelta = timedelta(days=7)) -> List[UsageAnomaly]:
        """Detect anomalies in usage patterns."""
        anomalies = []
        
        # Detect request count spikes
        spike_anomalies = await self._detect_request_spikes(time_range)
        anomalies.extend(spike_anomalies)
        
        # Detect latency spikes
        latency_anomalies = await self._detect_latency_spikes(time_range)
        anomalies.extend(latency_anomalies)
        
        # Detect error rate increases
        error_anomalies = await self._detect_error_rate_spikes(time_range)
        anomalies.extend(error_anomalies)
        
        # Sort by severity
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        anomalies.sort(key=lambda x: severity_order.get(x.severity, 0), reverse=True)
        
        return anomalies
    
    async def generate_tenant_report(self,
                                   tenant_id: str,
                                   time_range: timedelta = timedelta(days=30)) -> Dict[str, Any]:
        """Generate comprehensive analytics report for a tenant."""
        # Get basic usage stats
        usage_stats = await self.telemetry_store.get_tenant_usage(tenant_id, time_range)
        
        # Get model performance for models used by tenant
        model_performance = await self._get_tenant_model_performance(tenant_id, time_range)
        
        # Get cost optimization opportunities
        cost_opportunities = await self.identify_cost_optimization_opportunities(tenant_id, time_range)
        
        # Detect anomalies
        anomalies = await self._detect_tenant_anomalies(tenant_id, time_range)
        
        # Get task type breakdown
        task_breakdown = await self._get_tenant_task_breakdown(tenant_id, time_range)
        
        return {
            "tenant_id": tenant_id,
            "report_period": {
                "start": datetime.now() - time_range,
                "end": datetime.now()
            },
            "usage_statistics": usage_stats,
            "model_performance": model_performance,
            "task_breakdown": task_breakdown,
            "cost_optimization_opportunities": cost_opportunities[:10],  # Top 10
            "anomalies": anomalies[:5],  # Top 5
            "recommendations": await self._generate_tenant_recommendations(
                tenant_id, usage_stats, cost_opportunities, anomalies
            )
        }
    
    def _calculate_efficiency_score(self, performance: Dict[str, Any]) -> float:
        """Calculate overall efficiency score from performance metrics."""
        # Weight factors
        speed_weight = 0.3
        cost_weight = 0.3
        quality_weight = 0.25
        reliability_weight = 0.15
        
        # Normalize metrics (0-1 scale)
        speed_score = min(1000 / max(performance.get("avg_latency", 1000), 1), 1.0)
        cost_score = min(0.01 / max(performance.get("avg_cost", 0.01), 0.0001), 1.0)
        quality_score = performance.get("avg_quality", 0)
        reliability_score = performance.get("success_rate", 0)
        
        efficiency = (
            speed_score * speed_weight +
            cost_score * cost_weight +
            quality_score * quality_weight +
            reliability_score * reliability_weight
        )
        
        return min(max(efficiency, 0.0), 1.0)
    
    def _determine_performance_tier(self, efficiency_score: float) -> PerformanceTier:
        """Determine performance tier from efficiency score."""
        if efficiency_score >= 0.9:
            return PerformanceTier.EXCELLENT
        elif efficiency_score >= 0.75:
            return PerformanceTier.GOOD
        elif efficiency_score >= 0.6:
            return PerformanceTier.ACCEPTABLE
        elif efficiency_score >= 0.4:
            return PerformanceTier.POOR
        else:
            return PerformanceTier.UNACCEPTABLE
    
    async def _get_task_performance(self, model_id: str, time_range: timedelta) -> Dict[str, Dict[str, float]]:
        """Get task-specific performance for a model."""
        # This would query the telemetry store for task-specific metrics
        # For now, return placeholder data
        return {
            "chat": {"avg_quality": 0.8, "avg_latency": 500, "success_rate": 0.95},
            "coding": {"avg_quality": 0.7, "avg_latency": 800, "success_rate": 0.9},
            "qa": {"avg_quality": 0.85, "avg_latency": 400, "success_rate": 0.98}
        }
    
    async def _analyze_latency_trend(self, model_id: str, time_range: timedelta) -> str:
        """Analyze latency trend over time."""
        trends = await self.telemetry_store.get_latency_trends(model_id, time_range)
        
        if len(trends) < 2:
            return "stable"
        
        # Simple trend analysis
        recent_avg = trends[-1]["avg_latency"]
        older_avg = trends[0]["avg_latency"]
        
        change_pct = ((recent_avg - older_avg) / older_avg) * 100
        
        if change_pct > 10:
            return "degrading"
        elif change_pct < -10:
            return "improving"
        else:
            return "stable"
    
    async def _analyze_quality_trend(self, model_id: str, time_range: timedelta) -> str:
        """Analyze quality trend over time."""
        trends = await self.telemetry_store.get_quality_trends(time_range=time_range)
        
        if len(trends) < 2:
            return "stable"
        
        recent_avg = trends[-1]["avg_quality"]
        older_avg = trends[0]["avg_quality"]
        
        change_pct = ((recent_avg - older_avg) / older_avg) * 100
        
        if change_pct > 5:
            return "improving"
        elif change_pct < -5:
            return "degrading"
        else:
            return "stable"
    
    async def _analyze_cost_trend(self, model_id: str, time_range: timedelta) -> str:
        """Analyze cost trend over time."""
        # This would analyze cost trends from the telemetry store
        # For now, return stable
        return "stable"
    
    async def _generate_model_recommendations(self,
                                            model_id: str,
                                            performance: Dict[str, Any],
                                            task_performance: Dict[str, Dict[str, float]],
                                            time_range: timedelta) -> List[str]:
        """Generate recommendations for a model."""
        recommendations = []
        
        # Cache recommendations
        cache_hit_rate = performance.get("cache_hit_rate", 0)
        if cache_hit_rate < 0.3:
            recommendations.append("Consider enabling semantic caching to improve cache hit rate")
        
        # Quality recommendations
        avg_quality = performance.get("avg_quality", 0)
        if avg_quality < 0.7:
            recommendations.append("Quality score is below threshold - consider response validation")
        
        # Latency recommendations
        avg_latency = performance.get("avg_latency", 0)
        if avg_latency > 1000:
            recommendations.append("High latency detected - consider using faster models or caching")
        
        # Cost recommendations
        avg_cost = performance.get("avg_cost", 0)
        if avg_cost > 0.01:
            recommendations.append("High cost per request - consider local models or downgrading")
        
        # Success rate recommendations
        success_rate = performance.get("success_rate", 0)
        if success_rate < 0.95:
            recommendations.append("Low success rate - investigate error patterns and improve reliability")
        
        return recommendations
    
    async def _analyze_cache_optimization(self,
                                        tenant_id: Optional[str],
                                        time_range: timedelta) -> List[CostOptimization]:
        """Analyze cache optimization opportunities."""
        opportunities = []
        
        # This would analyze cache hit rates and potential savings
        # For now, return placeholder
        opportunities.append(CostOptimization(
            type="cache",
            description="Enable semantic caching to reduce redundant API calls",
            potential_savings_usd=100.0,
            implementation_effort="medium",
            impact_score=0.8
        ))
        
        return opportunities
    
    async def _analyze_local_model_opportunities(self,
                                               tenant_id: Optional[str],
                                               time_range: timedelta) -> List[CostOptimization]:
        """Analyze local model usage opportunities."""
        opportunities = []
        
        # This would identify tasks suitable for local models
        opportunities.append(CostOptimization(
            type="local_model",
            description="Use local models for simple chat tasks to reduce costs",
            potential_savings_usd=200.0,
            implementation_effort="low",
            impact_score=0.9
        ))
        
        return opportunities
    
    async def _analyze_model_downgrade_opportunities(self,
                                                    tenant_id: Optional[str],
                                                    time_range: timedelta) -> List[CostOptimization]:
        """Analyze model downgrade opportunities."""
        opportunities = []
        
        # This would identify opportunities to use cheaper models
        opportunities.append(CostOptimization(
            type="model_downgrade",
            description="Downgrade to smaller models for non-critical tasks",
            potential_savings_usd=150.0,
            implementation_effort="low",
            impact_score=0.7
        ))
        
        return opportunities
    
    async def _detect_request_spikes(self, time_range: timedelta) -> List[UsageAnomaly]:
        """Detect unusual request count spikes."""
        anomalies = []
        
        # This would analyze request patterns for spikes
        # For now, return placeholder
        anomalies.append(UsageAnomaly(
            timestamp=datetime.now() - timedelta(hours=2),
            anomaly_type="spike",
            description="Request count increased by 300% compared to baseline",
            severity="medium",
            affected_models=["gpt-4", "claude-3-sonnet"],
            metrics={"request_count": 1500, "baseline": 375}
        ))
        
        return anomalies
    
    async def _detect_latency_spikes(self, time_range: timedelta) -> List[UsageAnomaly]:
        """Detect unusual latency spikes."""
        anomalies = []
        
        # This would analyze latency patterns for spikes
        return anomalies
    
    async def _detect_error_rate_spikes(self, time_range: timedelta) -> List[UsageAnomaly]:
        """Detect unusual error rate increases."""
        anomalies = []
        
        # This would analyze error rate patterns
        return anomalies
    
    async def _get_tenant_model_performance(self,
                                          tenant_id: str,
                                          time_range: timedelta) -> List[Dict[str, Any]]:
        """Get model performance for models used by a tenant."""
        # This would query telemetry store for tenant-specific model performance
        return []
    
    async def _detect_tenant_anomalies(self,
                                      tenant_id: str,
                                      time_range: timedelta) -> List[UsageAnomaly]:
        """Detect anomalies specific to a tenant."""
        return []
    
    async def _get_tenant_task_breakdown(self,
                                        tenant_id: str,
                                        time_range: timedelta) -> Dict[str, Any]:
        """Get task type breakdown for a tenant."""
        return {}
    
    async def _generate_tenant_recommendations(self,
                                              tenant_id: str,
                                              usage_stats: Dict[str, Any],
                                              cost_opportunities: List[CostOptimization],
                                              anomalies: List[UsageAnomaly]) -> List[str]:
        """Generate recommendations for a tenant."""
        recommendations = []
        
        # Cost-based recommendations
        if cost_opportunities:
            recommendations.append(f"Implement top {min(3, len(cost_opportunities))} cost optimization opportunities")
        
        # Anomaly-based recommendations
        if anomalies:
            recommendations.append("Investigate and resolve detected usage anomalies")
        
        # Usage-based recommendations
        total_cost = usage_stats.get("total_cost", 0)
        if total_cost > 1000:
            recommendations.append("Consider budget management and cost controls")
        
        return recommendations
