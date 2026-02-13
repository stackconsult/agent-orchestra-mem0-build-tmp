"""
Analytics Engine

Provides real-time analytics, dashboards, and optimization recommendations
for enterprise tenants. Analyzes usage patterns, costs, and performance.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_, func

from .multi_tenancy import TenantContext, get_current_tenant
from .budget_management import BudgetManager, BudgetStatus
from .audit_logging import AuditLogger

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of optimization recommendations."""
    RETIRE_MODEL = "retire_model"
    DOWNGRADE_TO_LOCAL = "downgrade_to_local"
    ENABLE_CACHE = "enable_cache"
    ADJUST_POLICY = "adjust_policy"
    INCREASE_BUDGET = "increase_budget"
    OPTIMIZE_TASK_ROUTING = "optimize_task_routing"


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation for a tenant."""
    recommendation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    recommendation_type: RecommendationType = RecommendationType.ENABLE_CACHE
    
    # Recommendation details
    title: str = ""
    description: str = ""
    impact_estimate: str = ""
    savings_estimate_usd: Optional[float] = None
    
    # Target of recommendation
    target_model_id: Optional[str] = None
    target_task_type: Optional[str] = None
    target_team_id: Optional[str] = None
    target_project_id: Optional[str] = None
    
    # Metrics supporting recommendation
    current_metrics: Dict[str, float] = field(default_factory=dict)
    projected_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    confidence_score: float = 0.0  # 0.0 to 1.0
    priority: str = "medium"  # low, medium, high, critical
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Status
    status: str = "pending"  # pending, accepted, rejected, implemented
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommendation_id": self.recommendation_id,
            "tenant_id": self.tenant_id,
            "recommendation_type": self.recommendation_type.value,
            "title": self.title,
            "description": self.description,
            "impact_estimate": self.impact_estimate,
            "savings_estimate_usd": self.savings_estimate_usd,
            "target_model_id": self.target_model_id,
            "target_task_type": self.target_task_type,
            "target_team_id": self.target_team_id,
            "target_project_id": self.target_project_id,
            "current_metrics": self.current_metrics,
            "projected_metrics": self.projected_metrics,
            "confidence_score": self.confidence_score,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status
        }


@dataclass
class TenantDashboard:
    """Tenant analytics dashboard."""
    tenant_id: str = ""
    period_start: date = field(default_factory=date.today)
    period_end: date = field(default_factory=lambda: date.today() + timedelta(days=1))
    
    # Usage metrics
    total_requests: int = 0
    unique_users: int = 0
    unique_models: int = 0
    
    # Cost metrics
    total_cost_usd: float = 0.0
    average_cost_per_request: float = 0.0
    daily_average_cost: float = 0.0
    
    # Performance metrics
    average_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate: float = 0.0
    
    # Model usage breakdown
    model_usage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Task type breakdown
    task_usage: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Cache metrics
    cache_hit_rate: float = 0.0
    cache_savings_usd: float = 0.0
    
    # Budget status
    budget_status: Optional[BudgetStatus] = None
    
    # Quality metrics
    average_quality_score: float = 0.0
    validation_pass_rate: float = 0.0
    
    # Team breakdown (if applicable)
    team_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Recommendations
    recommendations: List[OptimizationRecommendation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat()
            },
            "usage": {
                "total_requests": self.total_requests,
                "unique_users": self.unique_users,
                "unique_models": self.unique_models
            },
            "costs": {
                "total_usd": self.total_cost_usd,
                "average_per_request": self.average_cost_per_request,
                "daily_average": self.daily_average_cost
            },
            "performance": {
                "average_latency_ms": self.average_latency_ms,
                "p95_latency_ms": self.p95_latency_ms,
                "p99_latency_ms": self.p99_latency_ms,
                "success_rate": self.success_rate
            },
            "model_usage": self.model_usage,
            "task_usage": self.task_usage,
            "cache": {
                "hit_rate": self.cache_hit_rate,
                "savings_usd": self.cache_savings_usd
            },
            "budget": self.budget_status.to_dict() if self.budget_status else None,
            "quality": {
                "average_score": self.average_quality_score,
                "validation_pass_rate": self.validation_pass_rate
            },
            "team_metrics": self.team_metrics,
            "recommendations": [r.to_dict() for r in self.recommendations]
        }


class AnalyticsEngine:
    """Analytics engine for enterprise insights."""
    
    def __init__(
        self,
        db_session_factory,
        budget_manager: BudgetManager,
        audit_logger: AuditLogger
    ):
        """Initialize analytics engine."""
        self.session_factory = db_session_factory
        self.budget_manager = budget_manager
        self.audit_logger = audit_logger
        
        # Recommendation cache
        self._recommendation_cache: Dict[str, List[OptimizationRecommendation]] = {}
        
        logger.info("AnalyticsEngine initialized")
    
    async def get_tenant_dashboard(
        self,
        tenant_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Optional[TenantDashboard]:
        """Get comprehensive tenant dashboard."""
        try:
            # Default to last 30 days
            if not start_date:
                start_date = date.today() - timedelta(days=30)
            if not end_date:
                end_date = date.today()
            
            dashboard = TenantDashboard(
                tenant_id=tenant_id,
                period_start=start_date,
                period_end=end_date
            )
            
            # Get usage metrics
            await self._populate_usage_metrics(dashboard)
            
            # Get cost metrics
            await self._populate_cost_metrics(dashboard)
            
            # Get performance metrics
            await self._populate_performance_metrics(dashboard)
            
            # Get model usage breakdown
            await self._populate_model_usage(dashboard)
            
            # Get task type breakdown
            await self._populate_task_usage(dashboard)
            
            # Get cache metrics
            await self._populate_cache_metrics(dashboard)
            
            # Get budget status
            dashboard.budget_status = await self.budget_manager.get_budget_status(
                tenant_id, BudgetLevel.TENANT
            )
            
            # Get quality metrics
            await self._populate_quality_metrics(dashboard)
            
            # Get team metrics
            await self._populate_team_metrics(dashboard)
            
            # Generate recommendations
            dashboard.recommendations = await self.generate_recommendations(tenant_id)
            
            return dashboard
            
        except Exception as e:
            logger.error(f"Error getting tenant dashboard: {e}")
            return None
    
    async def generate_recommendations(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations for a tenant."""
        try:
            # Check cache first
            cache_key = f"{tenant_id}:{date.today()}"
            if cache_key in self._recommendation_cache:
                return self._recommendation_cache[cache_key]
            
            recommendations = []
            
            # Analyze model usage for retirement candidates
            model_recs = await self._analyze_model_retirement(tenant_id)
            recommendations.extend(model_recs)
            
            # Analyze for local model opportunities
            local_recs = await self._analyze_local_model_opportunities(tenant_id)
            recommendations.extend(local_recs)
            
            # Analyze cache opportunities
            cache_recs = await self._analyze_cache_opportunities(tenant_id)
            recommendations.extend(cache_recs)
            
            # Analyze policy adjustments
            policy_recs = await self._analyze_policy_adjustments(tenant_id)
            recommendations.extend(policy_recs)
            
            # Analyze budget needs
            budget_recs = await self._analyze_budget_needs(tenant_id)
            recommendations.extend(budget_recs)
            
            # Sort by priority and confidence
            recommendations.sort(key=lambda r: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}[r.priority],
                r.confidence_score
            ), reverse=True)
            
            # Cache recommendations
            self._recommendation_cache[cache_key] = recommendations
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []
    
    async def get_model_analytics(
        self,
        tenant_id: str,
        model_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get detailed analytics for a specific model."""
        try:
            if not start_date:
                start_date = date.today() - timedelta(days=30)
            if not end_date:
                end_date = date.today()
            
            async with self.session_factory() as session:
                # Get model metrics
                query = text("""
                    SELECT 
                        COUNT(*) as request_count,
                        AVG(latency_ms) as avg_latency,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99_latency,
                        AVG(cost_usd) as avg_cost,
                        SUM(cost_usd) as total_cost,
                        AVG(quality_score) as avg_quality,
                        COUNTIF(success) / COUNT(*) as success_rate,
                        COUNTIF(cache_hit) / COUNT(*) as cache_hit_rate
                    FROM request_metrics
                    WHERE tenant_id = :tenant_id
                      AND model_id = :model_id
                      AND time >= :start_date
                      AND time < :end_date + INTERVAL '1 day'
                """)
                
                result = await session.execute(query, {
                    "tenant_id": tenant_id,
                    "model_id": model_id,
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                row = result.fetchone()
                
                if not row or row.request_count == 0:
                    return {"error": "No usage data found for model"}
                
                # Get task type breakdown
                task_query = text("""
                    SELECT task_type, COUNT(*) as count, AVG(cost_usd) as avg_cost
                    FROM request_metrics
                    WHERE tenant_id = :tenant_id
                      AND model_id = :model_id
                      AND time >= :start_date
                      AND time < :end_date + INTERVAL '1 day'
                    GROUP BY task_type
                    ORDER BY count DESC
                """)
                
                task_result = await session.execute(task_query, {
                    "tenant_id": tenant_id,
                    "model_id": model_id,
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                task_breakdown = {
                    row.task_type: {
                        "request_count": row.count,
                        "average_cost": float(row.avg_cost)
                    }
                    for row in task_result.fetchall()
                }
                
                return {
                    "model_id": model_id,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    },
                    "usage": {
                        "request_count": row.request_count,
                        "success_rate": float(row.success_rate),
                        "cache_hit_rate": float(row.cache_hit_rate)
                    },
                    "performance": {
                        "average_latency_ms": float(row.avg_latency),
                        "p95_latency_ms": float(row.p95_latency),
                        "p99_latency_ms": float(row.p99_latency)
                    },
                    "costs": {
                        "average_cost_usd": float(row.avg_cost),
                        "total_cost_usd": float(row.total_cost)
                    },
                    "quality": {
                        "average_score": float(row.avg_quality)
                    },
                    "task_breakdown": task_breakdown
                }
                
        except Exception as e:
            logger.error(f"Error getting model analytics: {e}")
            return {"error": str(e)}
    
    async def _populate_usage_metrics(self, dashboard: TenantDashboard):
        """Populate basic usage metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(DISTINCT model_id) as unique_models
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            row = result.fetchone()
            if row:
                dashboard.total_requests = row.total_requests or 0
                dashboard.unique_users = row.unique_users or 0
                dashboard.unique_models = row.unique_models or 0
    
    async def _populate_cost_metrics(self, dashboard: TenantDashboard):
        """Populate cost metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    SUM(cost_usd) as total_cost,
                    AVG(cost_usd) as avg_cost_per_request
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            row = result.fetchone()
            if row:
                dashboard.total_cost_usd = float(row.total_cost or 0)
                dashboard.average_cost_per_request = float(row.avg_cost_per_request or 0)
                
                # Calculate daily average
                days = (dashboard.period_end - dashboard.period_start).days or 1
                dashboard.daily_average_cost = dashboard.total_cost_usd / days
    
    async def _populate_performance_metrics(self, dashboard: TenantDashboard):
        """Populate performance metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    AVG(latency_ms) as avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) as p99_latency,
                    COUNTIF(success) / COUNT(*) as success_rate
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            row = result.fetchone()
            if row:
                dashboard.average_latency_ms = float(row.avg_latency or 0)
                dashboard.p95_latency_ms = float(row.p95_latency or 0)
                dashboard.p99_latency_ms = float(row.p99_latency or 0)
                dashboard.success_rate = float(row.success_rate or 0)
    
    async def _populate_model_usage(self, dashboard: TenantDashboard):
        """Populate model usage breakdown."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    model_id,
                    COUNT(*) as request_count,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency,
                    AVG(quality_score) as avg_quality
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
                GROUP BY model_id
                ORDER BY request_count DESC
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            for row in result.fetchall():
                dashboard.model_usage[row.model_id] = {
                    "request_count": row.request_count,
                    "total_cost_usd": float(row.total_cost),
                    "average_latency_ms": float(row.avg_latency),
                    "average_quality_score": float(row.avg_quality)
                }
    
    async def _populate_task_usage(self, dashboard: TenantDashboard):
        """Populate task type breakdown."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    task_type,
                    COUNT(*) as request_count,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency,
                    AVG(quality_score) as avg_quality
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
                GROUP BY task_type
                ORDER BY request_count DESC
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            for row in result.fetchall():
                dashboard.task_usage[row.task_type] = {
                    "request_count": row.request_count,
                    "total_cost_usd": float(row.total_cost),
                    "average_latency_ms": float(row.avg_latency),
                    "average_quality_score": float(row.avg_quality)
                }
    
    async def _populate_cache_metrics(self, dashboard: TenantDashboard):
        """Populate cache metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    COUNTIF(cache_hit) / COUNT(*) as cache_hit_rate,
                    SUM(cost_usd) * COUNTIF(cache_hit) / COUNT(*) as estimated_savings
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            row = result.fetchone()
            if row:
                dashboard.cache_hit_rate = float(row.cache_hit_rate or 0)
                dashboard.cache_savings_usd = float(row.estimated_savings or 0)
    
    async def _populate_quality_metrics(self, dashboard: TenantDashboard):
        """Populate quality metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    AVG(quality_score) as avg_quality,
                    COUNTIF(response_valid) / COUNT(*) as validation_pass_rate
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            row = result.fetchone()
            if row:
                dashboard.average_quality_score = float(row.avg_quality or 0)
                dashboard.validation_pass_rate = float(row.validation_pass_rate or 0)
    
    async def _populate_team_metrics(self, dashboard: TenantDashboard):
        """Populate team-level metrics."""
        async with self.session_factory() as session:
            query = text("""
                SELECT 
                    team_id,
                    COUNT(*) as request_count,
                    SUM(cost_usd) as total_cost,
                    AVG(latency_ms) as avg_latency
                FROM request_metrics
                WHERE tenant_id = :tenant_id
                  AND team_id IS NOT NULL
                  AND time >= :start_date
                  AND time < :end_date + INTERVAL '1 day'
                GROUP BY team_id
                ORDER BY request_count DESC
            """)
            
            result = await session.execute(query, {
                "tenant_id": dashboard.tenant_id,
                "start_date": dashboard.period_start,
                "end_date": dashboard.period_end
            })
            
            for row in result.fetchall():
                dashboard.team_metrics[row.team_id] = {
                    "request_count": row.request_count,
                    "total_cost_usd": float(row.total_cost),
                    "average_latency_ms": float(row.avg_latency)
                }
    
    async def _analyze_model_retirement(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Analyze models that could be retired."""
        recommendations = []
        
        try:
            async with self.session_factory() as session:
                # Find models with low usage or high cost
                query = text("""
                    SELECT 
                        model_id,
                        COUNT(*) as request_count,
                        SUM(cost_usd) as total_cost,
                        AVG(quality_score) as avg_quality
                    FROM request_metrics
                    WHERE tenant_id = :tenant_id
                      AND time >= NOW() - INTERVAL '30 days'
                    GROUP BY model_id
                    HAVING COUNT(*) < 10 OR SUM(cost_usd) > 100
                    ORDER BY total_cost DESC
                """)
                
                result = await session.execute(query, {"tenant_id": tenant_id})
                
                for row in result.fetchall():
                    if row.request_count < 10:
                        rec = OptimizationRecommendation(
                            tenant_id=tenant_id,
                            recommendation_type=RecommendationType.RETIRE_MODEL,
                            title=f"Retire unused model: {row.model_id}",
                            description=f"Model {row.model_id} has only {row.request_count} requests in 30 days",
                            impact_estimate=f"Reduce complexity and potential costs",
                            target_model_id=row.model_id,
                            current_metrics={"request_count": row.request_count, "total_cost": float(row.total_cost)},
                            confidence_score=0.8,
                            priority="low"
                        )
                        recommendations.append(rec)
                    
                    elif float(row.total_cost) > 100:
                        rec = OptimizationRecommendation(
                            tenant_id=tenant_id,
                            recommendation_type=RecommendationType.RETIRE_MODEL,
                            title=f"Review expensive model: {row.model_id}",
                            description=f"Model {row.model_id} costs ${row.total_cost:.2f} in 30 days",
                            impact_estimate=f"Potential significant cost savings",
                            target_model_id=row.model_id,
                            current_metrics={"request_count": row.request_count, "total_cost": float(row.total_cost)},
                            savings_estimate_usd=float(row.total_cost) * 0.5,  # Estimate 50% savings
                            confidence_score=0.6,
                            priority="medium"
                        )
                        recommendations.append(rec)
                        
        except Exception as e:
            logger.error(f"Error analyzing model retirement: {e}")
        
        return recommendations
    
    async def _analyze_local_model_opportunities(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Analyze opportunities to use local models."""
        recommendations = []
        
        try:
            async with self.session_factory() as session:
                # Find tasks using expensive cloud models that could use local models
                query = text("""
                    SELECT 
                        task_type,
                        model_id,
                        provider,
                        COUNT(*) as request_count,
                        SUM(cost_usd) as total_cost
                    FROM request_metrics
                    WHERE tenant_id = :tenant_id
                      AND provider != 'ollama'
                      AND time >= NOW() - INTERVAL '30 days'
                    GROUP BY task_type, model_id, provider
                    HAVING COUNT(*) > 20
                    ORDER BY total_cost DESC
                """)
                
                result = await session.execute(query, {"tenant_id": tenant_id})
                
                for row in result.fetchall():
                    rec = OptimizationRecommendation(
                        tenant_id=tenant_id,
                        recommendation_type=RecommendationType.DOWNGRADE_TO_LOCAL,
                        title=f"Use local models for {row.task_type}",
                        description=f"Task {row.task_type} uses {row.model_id} ({row.provider}) for {row.request_count} requests",
                        impact_estimate=f"Save ~{float(row.total_cost) * 0.9:.2f} USD/month",
                        target_task_type=row.task_type,
                        target_model_id=row.model_id,
                        current_metrics={"request_count": row.request_count, "total_cost": float(row.total_cost)},
                        projected_metrics={"estimated_savings": float(row.total_cost) * 0.9},
                        savings_estimate_usd=float(row.total_cost) * 0.9,
                        confidence_score=0.7,
                        priority="high"
                    )
                    recommendations.append(rec)
                    
        except Exception as e:
            logger.error(f"Error analyzing local model opportunities: {e}")
        
        return recommendations
    
    async def _analyze_cache_opportunities(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Analyze opportunities for semantic caching."""
        recommendations = []
        
        try:
            async with self.session_factory() as session:
                # Find task types with low cache hit rates
                query = text("""
                    SELECT 
                        task_type,
                        COUNT(*) as total_requests,
                        COUNTIF(cache_hit) as cache_hits,
                        SUM(cost_usd) as total_cost
                    FROM request_metrics
                    WHERE tenant_id = :tenant_id
                      AND time >= NOW() - INTERVAL '30 days'
                    GROUP BY task_type
                    HAVING COUNT(*) > 50
                      AND COUNTIF(cache_hit) / COUNT(*) < 0.3
                    ORDER BY total_cost DESC
                """)
                
                result = await session.execute(query, {"tenant_id": tenant_id})
                
                for row in result.fetchall():
                    cache_hit_rate = row.cache_hits / row.total_requests if row.total_requests > 0 else 0
                    potential_savings = float(row.total_cost) * 0.4  # Estimate 40% cache savings
                    
                    rec = OptimizationRecommendation(
                        tenant_id=tenant_id,
                        recommendation_type=RecommendationType.ENABLE_CACHE,
                        title=f"Enable semantic caching for {row.task_type}",
                        description=f"Task {row.task_type} has low cache hit rate ({cache_hit_rate:.1%})",
                        impact_estimate=f"Save ~{potential_savings:.2f} USD/month",
                        target_task_type=row.task_type,
                        current_metrics={
                            "cache_hit_rate": cache_hit_rate,
                            "request_count": row.total_requests,
                            "total_cost": float(row.total_cost)
                        },
                        projected_metrics={"estimated_cache_hit_rate": 0.5},
                        savings_estimate_usd=potential_savings,
                        confidence_score=0.8,
                        priority="high"
                    )
                    recommendations.append(rec)
                    
        except Exception as e:
            logger.error(f"Error analyzing cache opportunities: {e}")
        
        return recommendations
    
    async def _analyze_policy_adjustments(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Analyze policy adjustment opportunities."""
        recommendations = []
        
        # This would analyze current policy effectiveness
        # and suggest adjustments based on performance data
        
        return recommendations
    
    async def _analyze_budget_needs(self, tenant_id: str) -> List[OptimizationRecommendation]:
        """Analyze budget adjustment needs."""
        recommendations = []
        
        try:
            # Get budget status
            budget_status = await self.budget_manager.get_budget_status(
                tenant_id, BudgetLevel.TENANT
            )
            
            if budget_status and budget_status.monthly_status in [BudgetStatus.CRITICAL, BudgetStatus.EXCEEDED]:
                rec = OptimizationRecommendation(
                    tenant_id=tenant_id,
                    recommendation_type=RecommendationType.INCREASE_BUDGET,
                    title="Budget limit exceeded",
                    description=f"Monthly budget usage is {budget_status.monthly_usage_pct:.1f}%",
                    impact_estimate="Avoid service interruption",
                    current_metrics={"usage_pct": budget_status.monthly_usage_pct},
                    confidence_score=0.9,
                    priority="critical"
                )
                recommendations.append(rec)
                
        except Exception as e:
            logger.error(f"Error analyzing budget needs: {e}")
        
        return recommendations
