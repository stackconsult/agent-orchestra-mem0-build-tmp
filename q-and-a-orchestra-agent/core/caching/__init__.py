"""
Caching Module

Intelligent caching system with semantic similarity search,
vector database integration, and cache optimization.

Components:
- SemanticCache: Vector-based semantic caching
- VectorDBAdapter: Interface to vector databases
- CacheManager: Cache lifecycle and optimization
"""

from .semantic_cache import SemanticCache, CacheEntry, CacheHit
from .vector_db_adapter import VectorDBAdapter, WeaviateAdapter, PineconeAdapter
from .cache_manager import CacheManager, CacheStats, CacheOptimization

__all__ = [
    "SemanticCache",
    "CacheEntry", 
    "CacheHit",
    "VectorDBAdapter",
    "WeaviateAdapter",
    "PineconeAdapter",
    "CacheManager",
    "CacheStats",
    "CacheOptimization"
]
