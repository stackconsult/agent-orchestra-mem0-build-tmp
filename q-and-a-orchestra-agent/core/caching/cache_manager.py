"""
Cache Manager

Manages cache lifecycle, optimization, and coordination
between different caching strategies.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .semantic_cache import SemanticCache, CacheStrategy
from .vector_db_adapter import VectorDBAdapter


logger = logging.getLogger(__name__)


class CacheOptimizationType(str, Enum):
    """Types of cache optimization."""
    CLEANUP_EXPIRED = "cleanup_expired"
    REMOVE_LOW_QUALITY = "remove_low_quality"
    COMPRESS_RESPONSES = "compress_responses"
    REINDEX_VECTORS = "reindex_vectors"
    BALANCE_DISTRIBUTION = "balance_distribution"


@dataclass
class CacheStats:
    """Comprehensive cache statistics."""
    total_entries: int
    memory_entries: int
    vector_db_entries: int
    
    # Performance metrics
    hit_rate: float
    avg_similarity_score: float
    avg_response_time_ms: float
    
    # Storage metrics
    total_size_mb: float
    avg_entry_size_kb: float
    
    # Distribution metrics
    entries_by_task_type: Dict[str, int]
    entries_by_tenant: Dict[str, int]
    entries_by_model: Dict[str, int]
    
    # Age metrics
    avg_age_days: float
    oldest_entry_age_days: float
    
    # Quality metrics
    avg_quality_score: float
    low_quality_entries: int
    
    # Cost metrics
    total_cost_saved: float
    cost_saved_per_day: float
    
    timestamp: datetime


@dataclass
class CacheOptimization:
    """Cache optimization result."""
    optimization_type: CacheOptimizationType
    entries_processed: int
    space_freed_mb: float
    performance_improvement: float
    duration_seconds: float
    details: Dict[str, Any]


class CacheManager:
    """Manages semantic cache operations and optimization."""
    
    def __init__(self,
                 semantic_cache: SemanticCache,
                 optimization_interval_hours: int = 24,
                 auto_optimization: bool = True):
        """Initialize cache manager."""
        self.semantic_cache = semantic_cache
        self.optimization_interval = timedelta(hours=optimization_interval_hours)
        self.auto_optimization = auto_optimization
        
        # Optimization state
        self.last_optimization: Optional[datetime] = None
        self.optimization_running = False
        self.optimization_history: List[CacheOptimization] = []
        
        # Performance monitoring
        self.performance_metrics = {
            "total_requests": 0,
            "total_response_time_ms": 0.0,
            "optimization_time_saved_ms": 0.0
        }
        
        logger.info("Cache manager initialized")
    
    async def initialize(self):
        """Initialize cache manager."""
        await self.semantic_cache.initialize()
        
        # Schedule periodic optimization if enabled
        if self.auto_optimization:
            asyncio.create_task(self._periodic_optimization())
        
        logger.info("Cache manager fully initialized")
    
    async def get_cached_response(self,
                                 prompt: str,
                                 task_type: str,
                                 strategy: CacheStrategy = CacheStrategy.SEMANTIC_SIMILARITY,
                                 tenant_id: Optional[str] = None,
                                 user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cached response with performance tracking."""
        start_time = datetime.now()
        
        try:
            cache_hit = await self.semantic_cache.get(
                prompt=prompt,
                task_type=task_type,
                strategy=strategy,
                tenant_id=tenant_id,
                user_id=user_id
            )
            
            # Update performance metrics
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.performance_metrics["total_requests"] += 1
            self.performance_metrics["total_response_time_ms"] += response_time_ms
            
            if cache_hit:
                return {
                    "response": cache_hit.response,
                    "cache_hit": True,
                    "similarity_score": cache_hit.similarity_score,
                    "hit_type": cache_hit.hit_type,
                    "cost_saved": cache_hit.cost_saved,
                    "response_time_ms": response_time_ms,
                    "cache_entry": cache_hit.entry
                }
            else:
                return {
                    "response": None,
                    "cache_hit": False,
                    "response_time_ms": response_time_ms
                }
                
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return {
                "response": None,
                "cache_hit": False,
                "error": str(e),
                "response_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
    
    async def store_response(self,
                           prompt: str,
                           response: str,
                           task_type: str,
                           model_id: str,
                           cost_usd: float,
                           quality_score: float = 0.8,
                           tenant_id: Optional[str] = None,
                           user_id: Optional[str] = None,
                           session_id: Optional[str] = None) -> Dict[str, Any]:
        """Store response in cache with performance tracking."""
        start_time = datetime.now()
        
        try:
            cache_key = await self.semantic_cache.put(
                prompt=prompt,
                response=response,
                task_type=task_type,
                model_id=model_id,
                cost_usd=cost_usd,
                quality_score=quality_score,
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id
            )
            
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "cache_key": cache_key,
                "success": True,
                "response_time_ms": response_time_ms
            }
            
        except Exception as e:
            logger.error(f"Cache store error: {e}")
            return {
                "cache_key": None,
                "success": False,
                "error": str(e),
                "response_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
    
    async def invalidate_cache(self,
                             cache_key: Optional[str] = None,
                             task_type: Optional[str] = None,
                             tenant_id: Optional[str] = None,
                             older_than_days: Optional[int] = None) -> Dict[str, Any]:
        """Invalidate cache entries."""
        try:
            invalidated_count = await self.semantic_cache.invalidate(
                cache_key=cache_key,
                task_type=task_type,
                tenant_id=tenant_id,
                older_than_days=older_than_days
            )
            
            return {
                "success": True,
                "invalidated_count": invalidated_count,
                "criteria": {
                    "cache_key": cache_key,
                    "task_type": task_type,
                    "tenant_id": tenant_id,
                    "older_than_days": older_than_days
                }
            }
            
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "invalidated_count": 0
            }
    
    async def get_comprehensive_stats(self) -> CacheStats:
        """Get comprehensive cache statistics."""
        # Get basic cache stats
        cache_stats = await self.semantic_cache.get_cache_stats()
        
        # Get vector database stats
        vector_db_stats = cache_stats["vector_database"]
        
        # Calculate performance metrics
        total_requests = self.performance_metrics["total_requests"]
        avg_response_time = (
            self.performance_metrics["total_response_time_ms"] / total_requests
            if total_requests > 0 else 0
        )
        
        # Get distribution metrics (would need to query vector DB)
        entries_by_task_type = {}  # Placeholder
        entries_by_tenant = {}     # Placeholder
        entries_by_model = {}      # Placeholder
        
        # Calculate age metrics
        avg_age_days = 15.0  # Placeholder - would calculate from actual data
        oldest_entry_age_days = 30.0  # Placeholder
        
        # Calculate quality metrics
        avg_quality_score = cache_stats["cache_statistics"].get("avg_similarity_score", 0.8)
        low_quality_entries = 0  # Placeholder
        
        # Calculate cost metrics
        total_cost_saved = cache_stats["cache_statistics"].get("total_cost_saved", 0.0)
        cost_saved_per_day = total_cost_saved / max(avg_age_days, 1)
        
        # Calculate storage metrics
        total_size_mb = vector_db_stats.get("size", 0) * 0.001  # Rough estimate
        total_entries = vector_db_stats.get("size", 0)
        avg_entry_size_kb = (total_size_mb * 1024) / max(total_entries, 1)
        
        return CacheStats(
            total_entries=total_entries,
            memory_entries=cache_stats["memory_cache_size"],
            vector_db_entries=vector_db_stats.get("size", 0),
            
            hit_rate=cache_stats["cache_statistics"]["cache_hit_rate"],
            avg_similarity_score=cache_stats["cache_statistics"]["avg_similarity_score"],
            avg_response_time_ms=avg_response_time,
            
            total_size_mb=total_size_mb,
            avg_entry_size_kb=avg_entry_size_kb,
            
            entries_by_task_type=entries_by_task_type,
            entries_by_tenant=entries_by_tenant,
            entries_by_model=entries_by_model,
            
            avg_age_days=avg_age_days,
            oldest_entry_age_days=oldest_entry_age_days,
            
            avg_quality_score=avg_quality_score,
            low_quality_entries=low_quality_entries,
            
            total_cost_saved=total_cost_saved,
            cost_saved_per_day=cost_saved_per_day,
            
            timestamp=datetime.now()
        )
    
    async def run_optimization(self,
                             optimization_types: Optional[List[CacheOptimizationType]] = None) -> List[CacheOptimization]:
        """Run cache optimizations."""
        if self.optimization_running:
            logger.warning("Optimization already running")
            return []
        
        self.optimization_running = True
        start_time = datetime.now()
        
        try:
            if optimization_types is None:
                optimization_types = [
                    CacheOptimizationType.CLEANUP_EXPIRED,
                    CacheOptimizationType.REMOVE_LOW_QUALITY
                ]
            
            results = []
            
            for opt_type in optimization_types:
                result = await self._run_optimization_type(opt_type)
                results.append(result)
            
            self.last_optimization = datetime.now()
            self.optimization_history.extend(results)
            
            # Keep only last 30 days of history
            cutoff_date = datetime.now() - timedelta(days=30)
            self.optimization_history = [
                opt for opt in self.optimization_history
                if opt.timestamp > cutoff_date
            ]
            
            total_duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Cache optimization completed in {total_duration:.2f}s")
            
            return results
            
        finally:
            self.optimization_running = False
    
    async def _run_optimization_type(self, opt_type: CacheOptimizationType) -> CacheOptimization:
        """Run a specific optimization type."""
        start_time = datetime.now()
        
        if opt_type == CacheOptimizationType.CLEANUP_EXPIRED:
            return await self._cleanup_expired_entries(start_time)
        elif opt_type == CacheOptimizationType.REMOVE_LOW_QUALITY:
            return await self._remove_low_quality_entries(start_time)
        elif opt_type == CacheOptimizationType.COMPRESS_RESPONSES:
            return await self._compress_responses(start_time)
        elif opt_type == CacheOptimizationType.REINDEX_VECTORS:
            return await self._reindex_vectors(start_time)
        elif opt_type == CacheOptimizationType.BALANCE_DISTRIBUTION:
            return await self._balance_distribution(start_time)
        else:
            raise ValueError(f"Unknown optimization type: {opt_type}")
    
    async def _cleanup_expired_entries(self, start_time: datetime) -> CacheOptimization:
        """Clean up expired cache entries."""
        ttl_days = self.semantic_cache.ttl_days
        invalidated_count = await self.semantic_cache.invalidate(older_than_days=ttl_days)
        
        duration = (datetime.now() - start_time).total_seconds()
        space_freed = invalidated_count * 0.001  # Rough estimate in MB
        
        return CacheOptimization(
            optimization_type=CacheOptimizationType.CLEANUP_EXPIRED,
            entries_processed=invalidated_count,
            space_freed_mb=space_freed,
            performance_improvement=0.05,  # 5% improvement estimate
            duration_seconds=duration,
            details={
                "ttl_days": ttl_days,
                "space_freed_per_entry_kb": (space_freed * 1024) / max(invalidated_count, 1)
            }
        )
    
    async def _remove_low_quality_entries(self, start_time: datetime) -> CacheOptimization:
        """Remove low quality cache entries."""
        # This would require implementing quality-based deletion
        # For now, return placeholder
        duration = (datetime.now() - start_time).total_seconds()
        
        return CacheOptimization(
            optimization_type=CacheOptimizationType.REMOVE_LOW_QUALITY,
            entries_processed=0,
            space_freed_mb=0.0,
            performance_improvement=0.0,
            duration_seconds=duration,
            details={"quality_threshold": 0.3}
        )
    
    async def _compress_responses(self, start_time: datetime) -> CacheOptimization:
        """Compress stored responses to save space."""
        # This would require implementing response compression
        duration = (datetime.now() - start_time).total_seconds()
        
        return CacheOptimization(
            optimization_type=CacheOptimizationType.COMPRESS_RESPONSES,
            entries_processed=0,
            space_freed_mb=0.0,
            performance_improvement=0.0,
            duration_seconds=duration,
            details={"compression_algorithm": "gzip"}
        )
    
    async def _reindex_vectors(self, start_time: datetime) -> CacheOptimization:
        """Reindex vector database for better performance."""
        # This would require vector DB-specific reindexing
        duration = (datetime.now() - start_time).total_seconds()
        
        return CacheOptimization(
            optimization_type=CacheOptimizationType.REINDEX_VECTORS,
            entries_processed=0,
            space_freed_mb=0.0,
            performance_improvement=0.1,  # 10% improvement estimate
            duration_seconds=duration,
            details={"reindex_method": "full_rebuild"}
        )
    
    async def _balance_distribution(self, start_time: datetime) -> CacheOptimization:
        """Balance cache distribution across tasks/tenants."""
        # This would require analyzing and rebalancing distribution
        duration = (datetime.now() - start_time).total_seconds()
        
        return CacheOptimization(
            optimization_type=CacheOptimizationType.BALANCE_DISTRIBUTION,
            entries_processed=0,
            space_freed_mb=0.0,
            performance_improvement=0.0,
            duration_seconds=duration,
            details={"balance_strategy": "equal_distribution"}
        )
    
    async def _periodic_optimization(self):
        """Run periodic optimization in background."""
        while True:
            try:
                await asyncio.sleep(self.optimization_interval.total_seconds())
                
                if self.auto_optimization and not self.optimization_running:
                    logger.info("Starting periodic cache optimization")
                    await self.run_optimization()
                    
            except Exception as e:
                logger.error(f"Periodic optimization error: {e}")
    
    def get_optimization_history(self,
                               limit: int = 10) -> List[CacheOptimization]:
        """Get optimization history."""
        return self.optimization_history[-limit:]
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get optimization recommendations based on current stats."""
        recommendations = []
        
        # Get current stats
        stats = asyncio.create_task(self.get_comprehensive_stats())
        
        # Analyze and make recommendations
        # This is a placeholder - would analyze actual stats
        
        if stats.hit_rate() < 0.3:
            recommendations.append({
                "type": "increase_similarity_threshold",
                "description": "Cache hit rate is low, consider lowering similarity threshold",
                "priority": "high",
                "estimated_impact": "15-25% improvement in hit rate"
            })
        
        if stats.avg_age_days > 20:
            recommendations.append({
                "type": "reduce_ttl",
                "description": "Average cache age is high, consider reducing TTL",
                "priority": "medium",
                "estimated_impact": "10-15% reduction in storage costs"
            })
        
        if stats.low_quality_entries > stats.total_entries * 0.1:
            recommendations.append({
                "type": "quality_cleanup",
                "description": "High number of low-quality entries, run quality cleanup",
                "priority": "medium",
                "estimated_impact": "5-10% improvement in cache quality"
            })
        
        return recommendations
    
    def configure_optimization(self,
                             interval_hours: Optional[int] = None,
                             auto_optimization: Optional[bool] = None):
        """Configure optimization settings."""
        if interval_hours is not None:
            self.optimization_interval = timedelta(hours=interval_hours)
            logger.info(f"Optimization interval set to {interval_hours} hours")
        
        if auto_optimization is not None:
            self.auto_optimization = auto_optimization
            logger.info(f"Auto-optimization {'enabled' if auto_optimization else 'disabled'}")
    
    async def export_cache_data(self) -> Dict[str, Any]:
        """Export cache data for analysis."""
        cache_data = await self.semantic_cache.export_cache_data()
        stats = await self.get_comprehensive_stats()
        
        return {
            "export_timestamp": datetime.now().isoformat(),
            "statistics": stats.__dict__,
            "cache_entries": cache_data,
            "optimization_history": [
                {
                    "type": opt.optimization_type.value,
                    "entries_processed": opt.entries_processed,
                    "space_freed_mb": opt.space_freed_mb,
                    "performance_improvement": opt.performance_improvement,
                    "duration_seconds": opt.duration_seconds,
                    "timestamp": opt.timestamp.isoformat()
                }
                for opt in self.optimization_history
            ]
        }
    
    def get_manager_status(self) -> Dict[str, Any]:
        """Get cache manager status."""
        return {
            "auto_optimization": self.auto_optimization,
            "optimization_interval_hours": self.optimization_interval.total_seconds() / 3600,
            "last_optimization": self.last_optimization.isoformat() if self.last_optimization else None,
            "optimization_running": self.optimization_running,
            "optimization_count": len(self.optimization_history),
            "performance_metrics": self.performance_metrics
        }
