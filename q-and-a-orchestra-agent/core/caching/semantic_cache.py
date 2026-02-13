"""
Semantic Cache

Vector-based semantic caching that finds similar prompts
to avoid redundant API calls and improve response times.
"""

import asyncio
import hashlib
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sentence_transformers import SentenceTransformer
from .vector_db_adapter import VectorDBAdapter


logger = logging.getLogger(__name__)


class CacheStrategy(str, Enum):
    """Caching strategies."""
    EXACT_MATCH = "exact_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    HYBRID = "hybrid"


@dataclass
class CacheEntry:
    """Cache entry with semantic information."""
    cache_key: str
    original_prompt: str
    embedding: np.ndarray
    response: str
    task_type: str
    model_id: str
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_hit: Optional[datetime] = None
    hit_count: int = 0
    expires_at: Optional[datetime] = None
    
    # Quality metrics
    quality_score: float = 0.0
    similarity_threshold: float = 0.95
    cost_saved: float = 0.0
    
    # Context
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def update_hit(self, similarity_score: float = 1.0):
        """Update hit statistics."""
        self.hit_count += 1
        self.last_hit = datetime.now()
        self.quality_score = (self.quality_score + similarity_score) / 2
    
    def get_age_days(self) -> float:
        """Get age of cache entry in days."""
        return (datetime.now() - self.created_at).days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "cache_key": self.cache_key,
            "original_prompt": self.original_prompt,
            "embedding": self.embedding.tolist(),
            "response": self.response,
            "task_type": self.task_type,
            "model_id": self.model_id,
            "created_at": self.created_at.isoformat(),
            "last_hit": self.last_hit.isoformat() if self.last_hit else None,
            "hit_count": self.hit_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "quality_score": self.quality_score,
            "similarity_threshold": self.similarity_threshold,
            "cost_saved": self.cost_saved,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id
        }


@dataclass
class CacheHit:
    """Cache hit result."""
    entry: CacheEntry
    similarity_score: float
    hit_type: str  # "exact", "semantic"
    response: str
    cost_saved: float
    
    def get_cache_efficiency_score(self) -> float:
        """Calculate cache efficiency score."""
        base_score = 0.9 if self.hit_type == "exact" else 0.7
        similarity_bonus = self.similarity_score * 0.2
        return min(base_score + similarity_bonus, 1.0)


class SemanticCache:
    """Semantic cache with vector similarity search."""
    
    def __init__(self,
                 vector_db: VectorDBAdapter,
                 model_name: str = "all-MiniLM-L6-v2",
                 similarity_threshold: float = 0.95,
                 max_cache_size: int = 10000,
                 ttl_days: int = 30):
        """Initialize semantic cache."""
        self.vector_db = vector_db
        self.similarity_threshold = similarity_threshold
        self.max_cache_size = max_cache_size
        self.ttl_days = ttl_days
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(model_name)
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # Cache statistics
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "exact_hits": 0,
            "semantic_hits": 0,
            "total_cost_saved": 0.0,
            "avg_similarity_score": 0.0,
            "cache_hit_rate": 0.0
        }
        
        # In-memory cache for frequently accessed entries
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.memory_cache_size = 1000
        
        logger.info(f"Semantic cache initialized with model {model_name}")
    
    async def initialize(self):
        """Initialize cache and vector database."""
        await self.vector_db.initialize()
        logger.info("Semantic cache fully initialized")
    
    async def get(self,
                  prompt: str,
                  task_type: str,
                  strategy: CacheStrategy = CacheStrategy.SEMANTIC_SIMILARITY,
                  tenant_id: Optional[str] = None,
                  user_id: Optional[str] = None) -> Optional[CacheHit]:
        """Get cached response for prompt."""
        self.stats["total_requests"] += 1
        
        # Generate cache key
        cache_key = self._generate_cache_key(prompt, task_type, tenant_id)
        
        # Check memory cache first
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]
            if not entry.is_expired():
                entry.update_hit(1.0)
                self._update_hit_stats("exact", 1.0)
                return CacheHit(
                    entry=entry,
                    similarity_score=1.0,
                    hit_type="exact",
                    response=entry.response,
                    cost_saved=entry.cost_saved
                )
        
        # Check vector database
        if strategy == CacheStrategy.EXACT_MATCH:
            return await self._get_exact_match(prompt, task_type, tenant_id, user_id)
        elif strategy == CacheStrategy.SEMANTIC_SIMILARITY:
            return await self._get_semantic_match(prompt, task_type, tenant_id, user_id)
        elif strategy == CacheStrategy.HYBRID:
            return await self._get_hybrid_match(prompt, task_type, tenant_id, user_id)
        else:
            raise ValueError(f"Unknown cache strategy: {strategy}")
    
    async def _get_exact_match(self,
                             prompt: str,
                             task_type: str,
                             tenant_id: Optional[str] = None,
                             user_id: Optional[str] = None) -> Optional[CacheHit]:
        """Get exact match from cache."""
        cache_key = self._generate_cache_key(prompt, task_type, tenant_id)
        
        # Query vector database for exact match
        embedding = self._generate_embedding(prompt)
        results = await self.vector_db.search_similar(
            embedding=embedding,
            task_type=task_type,
            tenant_id=tenant_id,
            limit=1,
            similarity_threshold=1.0  # Exact match
        )
        
        if results:
            result = results[0]
            entry_data = result["metadata"]
            
            # Verify exact prompt match
            if entry_data["original_prompt"] == prompt:
                entry = self._reconstruct_entry(entry_data)
                
                # Update hit statistics
                entry.update_hit(1.0)
                self._update_hit_stats("exact", 1.0)
                
                # Update memory cache
                self._update_memory_cache(entry)
                
                return CacheHit(
                    entry=entry,
                    similarity_score=1.0,
                    hit_type="exact",
                    response=entry.response,
                    cost_saved=entry.cost_saved
                )
        
        self.stats["cache_misses"] += 1
        return None
    
    async def _get_semantic_match(self,
                                prompt: str,
                                task_type: str,
                                tenant_id: Optional[str] = None,
                                user_id: Optional[str] = None) -> Optional[CacheHit]:
        """Get semantic match from cache."""
        embedding = self._generate_embedding(prompt)
        
        # Query vector database for similar entries
        results = await self.vector_db.search_similar(
            embedding=embedding,
            task_type=task_type,
            tenant_id=tenant_id,
            limit=5,
            similarity_threshold=self.similarity_threshold
        )
        
        if results:
            # Get best match
            best_result = max(results, key=lambda x: x["similarity"])
            similarity_score = best_result["similarity"]
            
            if similarity_score >= self.similarity_threshold:
                entry_data = best_result["metadata"]
                entry = self._reconstruct_entry(entry_data)
                
                # Update hit statistics
                entry.update_hit(similarity_score)
                self._update_hit_stats("semantic", similarity_score)
                
                # Update memory cache
                self._update_memory_cache(entry)
                
                return CacheHit(
                    entry=entry,
                    similarity_score=similarity_score,
                    hit_type="semantic",
                    response=entry.response,
                    cost_saved=entry.cost_saved * similarity_score  # Scale by similarity
                )
        
        self.stats["cache_misses"] += 1
        return None
    
    async def _get_hybrid_match(self,
                              prompt: str,
                              task_type: str,
                              tenant_id: Optional[str] = None,
                              user_id: Optional[str] = None) -> Optional[CacheHit]:
        """Get hybrid match (exact + semantic)."""
        # Try exact match first
        exact_hit = await self._get_exact_match(prompt, task_type, tenant_id, user_id)
        if exact_hit:
            return exact_hit
        
        # Fall back to semantic match
        return await self._get_semantic_match(prompt, task_type, tenant_id, user_id)
    
    async def put(self,
                  prompt: str,
                  response: str,
                  task_type: str,
                  model_id: str,
                  cost_usd: float,
                  quality_score: float = 0.8,
                  tenant_id: Optional[str] = None,
                  user_id: Optional[str] = None,
                  session_id: Optional[str] = None) -> str:
        """Store response in cache."""
        # Generate cache key and embedding
        cache_key = self._generate_cache_key(prompt, task_type, tenant_id)
        embedding = self._generate_embedding(prompt)
        
        # Calculate expiration
        expires_at = datetime.now() + timedelta(days=self.ttl_days)
        
        # Create cache entry
        entry = CacheEntry(
            cache_key=cache_key,
            original_prompt=prompt,
            embedding=embedding,
            response=response,
            task_type=task_type,
            model_id=model_id,
            expires_at=expires_at,
            quality_score=quality_score,
            cost_saved=cost_usd,
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id
        )
        
        # Store in vector database
        await self.vector_db.store_embedding(
            cache_key=cache_key,
            embedding=embedding,
            metadata=entry.to_dict()
        )
        
        # Update memory cache
        self._update_memory_cache(entry)
        
        # Check cache size and cleanup if needed
        await self._cleanup_if_needed()
        
        logger.debug(f"Cached response for {task_type} task with key {cache_key}")
        return cache_key
    
    async def invalidate(self,
                        cache_key: Optional[str] = None,
                        task_type: Optional[str] = None,
                        tenant_id: Optional[str] = None,
                        older_than_days: Optional[int] = None) -> int:
        """Invalidate cache entries."""
        invalidated_count = 0
        
        if cache_key:
            # Invalidate specific entry
            await self.vector_db.delete_embedding(cache_key)
            self.memory_cache.pop(cache_key, None)
            invalidated_count = 1
        elif older_than_days:
            # Invalidate old entries
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            invalidated_count = await self.vector_db.delete_old_entries(cutoff_date)
            
            # Clear memory cache of old entries
            keys_to_remove = [
                key for key, entry in self.memory_cache.items()
                if entry.created_at < cutoff_date
            ]
            for key in keys_to_remove:
                del self.memory_cache[key]
        elif task_type or tenant_id:
            # Invalidate by task type or tenant
            invalidated_count = await self.vector_db.delete_by_filter(
                task_type=task_type,
                tenant_id=tenant_id
            )
            
            # Clear memory cache
            keys_to_remove = [
                key for key, entry in self.memory_cache.items()
                if (task_type and entry.task_type == task_type) or
                (tenant_id and entry.tenant_id == tenant_id)
            ]
            for key in keys_to_remove:
                del self.memory_cache[key]
        
        logger.info(f"Invalidated {invalidated_count} cache entries")
        return invalidated_count
    
    def _generate_cache_key(self, prompt: str, task_type: str, tenant_id: Optional[str] = None) -> str:
        """Generate cache key for prompt."""
        key_data = f"{prompt}:{task_type}:{tenant_id or 'default'}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        return self.embedding_model.encode(text, convert_to_numpy=True)
    
    def _reconstruct_entry(self, entry_data: Dict[str, Any]) -> CacheEntry:
        """Reconstruct CacheEntry from stored data."""
        return CacheEntry(
            cache_key=entry_data["cache_key"],
            original_prompt=entry_data["original_prompt"],
            embedding=np.array(entry_data["embedding"]),
            response=entry_data["response"],
            task_type=entry_data["task_type"],
            model_id=entry_data["model_id"],
            created_at=datetime.fromisoformat(entry_data["created_at"]),
            last_hit=datetime.fromisoformat(entry_data["last_hit"]) if entry_data["last_hit"] else None,
            hit_count=entry_data["hit_count"],
            expires_at=datetime.fromisoformat(entry_data["expires_at"]) if entry_data["expires_at"] else None,
            quality_score=entry_data["quality_score"],
            similarity_threshold=entry_data["similarity_threshold"],
            cost_saved=entry_data["cost_saved"],
            tenant_id=entry_data.get("tenant_id"),
            user_id=entry_data.get("user_id"),
            session_id=entry_data.get("session_id")
        )
    
    def _update_memory_cache(self, entry: CacheEntry):
        """Update memory cache with entry."""
        # Remove oldest entry if cache is full
        if len(self.memory_cache) >= self.memory_cache_size:
            oldest_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k].last_hit or datetime.min
            )
            del self.memory_cache[oldest_key]
        
        self.memory_cache[entry.cache_key] = entry
    
    def _update_hit_stats(self, hit_type: str, similarity_score: float):
        """Update hit statistics."""
        self.stats["cache_hits"] += 1
        
        if hit_type == "exact":
            self.stats["exact_hits"] += 1
        else:
            self.stats["semantic_hits"] += 1
        
        # Update average similarity
        current_avg = self.stats["avg_similarity_score"]
        total_hits = self.stats["cache_hits"]
        self.stats["avg_similarity_score"] = (
            (current_avg * (total_hits - 1) + similarity_score) / total_hits
        )
        
        # Update hit rate
        self.stats["cache_hit_rate"] = self.stats["cache_hits"] / self.stats["total_requests"]
    
    async def _cleanup_if_needed(self):
        """Clean up cache if it exceeds size limits."""
        # Check vector database size
        cache_size = await self.vector_db.get_collection_size()
        
        if cache_size > self.max_cache_size:
            # Remove oldest entries
            entries_to_remove = cache_size - self.max_cache_size + 1000  # Remove extra to avoid frequent cleanup
            
            # Get oldest entries
            oldest_entries = await self.vector_db.get_oldest_entries(entries_to_remove)
            
            # Delete them
            for entry in oldest_entries:
                await self.vector_db.delete_embedding(entry["cache_key"])
                self.memory_cache.pop(entry["cache_key"], None)
            
            logger.info(f"Cleaned up {entries_to_remove} old cache entries")
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        # Update hit rate
        if self.stats["total_requests"] > 0:
            self.stats["cache_hit_rate"] = self.stats["cache_hits"] / self.stats["total_requests"]
        
        # Get vector database stats
        db_stats = await self.vector_db.get_stats()
        
        return {
            "cache_statistics": self.stats.copy(),
            "vector_database": db_stats,
            "memory_cache_size": len(self.memory_cache),
            "similarity_threshold": self.similarity_threshold,
            "max_cache_size": self.max_cache_size,
            "ttl_days": self.ttl_days
        }
    
    async def optimize_cache(self) -> Dict[str, Any]:
        """Optimize cache performance."""
        optimization_results = {
            "entries_removed": 0,
            "space_freed_mb": 0.0,
            "optimizations_applied": []
        }
        
        # Remove expired entries
        expired_count = await self.invalidate(older_than_days=self.ttl_days)
        optimization_results["entries_removed"] += expired_count
        optimization_results["optimizations_applied"].append("expired_entries_removed")
        
        # Remove low-quality entries (low hit count, old age)
        low_quality_threshold = 0.3
        old_age_days = self.ttl_days // 2
        
        # This would require implementing a more sophisticated cleanup
        # For now, just log the optimization
        logger.info("Cache optimization completed")
        
        return optimization_results
    
    async def export_cache_data(self) -> List[Dict[str, Any]]:
        """Export cache data for backup or analysis."""
        # Get all entries from vector database
        all_entries = await self.vector_db.get_all_entries()
        
        exported_data = []
        for entry in all_entries:
            metadata = entry["metadata"]
            exported_data.append({
                "cache_key": metadata["cache_key"],
                "original_prompt": metadata["original_prompt"],
                "response": metadata["response"],
                "task_type": metadata["task_type"],
                "model_id": metadata["model_id"],
                "created_at": metadata["created_at"],
                "hit_count": metadata["hit_count"],
                "quality_score": metadata["quality_score"],
                "cost_saved": metadata["cost_saved"],
                "tenant_id": metadata.get("tenant_id")
            })
        
        return exported_data
    
    def set_similarity_threshold(self, threshold: float):
        """Update similarity threshold."""
        self.similarity_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Similarity threshold updated to {self.similarity_threshold}")
    
    def set_ttl_days(self, days: int):
        """Update TTL in days."""
        self.ttl_days = max(1, days)
        logger.info(f"TTL updated to {self.ttl_days} days")
    
    def set_max_cache_size(self, size: int):
        """Update maximum cache size."""
        self.max_cache_size = max(100, size)
        logger.info(f"Max cache size updated to {self.max_cache_size}")
