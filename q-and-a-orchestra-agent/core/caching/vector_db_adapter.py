"""
Vector Database Adapter

Abstract interface and implementations for vector databases
used in semantic caching and similarity search.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

try:
    import weaviate
    from weaviate.client import Client as WeaviateClient
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

try:
    import pinecone
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False


logger = logging.getLogger(__name__)


class VectorDBType(str):
    """Supported vector database types."""
    WEAVIATE = "weaviate"
    PINECONE = "pinecone"
    MEMORY = "memory"


class VectorDBAdapter(ABC):
    """Abstract interface for vector databases."""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the vector database connection."""
        pass
    
    @abstractmethod
    async def store_embedding(self,
                            cache_key: str,
                            embedding: np.ndarray,
                            metadata: Dict[str, Any]) -> bool:
        """Store embedding with metadata."""
        pass
    
    @abstractmethod
    async def search_similar(self,
                          embedding: np.ndarray,
                          task_type: Optional[str] = None,
                          tenant_id: Optional[str] = None,
                          limit: int = 10,
                          similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar embeddings."""
        pass
    
    @abstractmethod
    async def delete_embedding(self, cache_key: str) -> bool:
        """Delete embedding by cache key."""
        pass
    
    @abstractmethod
    async def delete_by_filter(self,
                             task_type: Optional[str] = None,
                             tenant_id: Optional[str] = None) -> int:
        """Delete embeddings by filter criteria."""
        pass
    
    @abstractmethod
    async def delete_old_entries(self, cutoff_date: datetime) -> int:
        """Delete entries older than cutoff date."""
        pass
    
    @abstractmethod
    async def get_collection_size(self) -> int:
        """Get total number of stored embeddings."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        pass


class MemoryVectorDB(VectorDBAdapter):
    """In-memory vector database for testing and development."""
    
    def __init__(self):
        """Initialize in-memory vector database."""
        self.embeddings: Dict[str, Tuple[np.ndarray, Dict[str, Any]]] = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize the in-memory database."""
        self.initialized = True
        logger.info("In-memory vector database initialized")
    
    async def store_embedding(self,
                            cache_key: str,
                            embedding: np.ndarray,
                            metadata: Dict[str, Any]) -> bool:
        """Store embedding in memory."""
        self.embeddings[cache_key] = (embedding, metadata)
        return True
    
    async def search_similar(self,
                          embedding: np.ndarray,
                          task_type: Optional[str] = None,
                          tenant_id: Optional[str] = None,
                          limit: int = 10,
                          similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar embeddings using cosine similarity."""
        results = []
        
        for cache_key, (stored_embedding, metadata) in self.embeddings.items():
            # Apply filters
            if task_type and metadata.get("task_type") != task_type:
                continue
            if tenant_id and metadata.get("tenant_id") != tenant_id:
                continue
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(embedding, stored_embedding)
            
            if similarity >= similarity_threshold:
                results.append({
                    "cache_key": cache_key,
                    "similarity": similarity,
                    "metadata": metadata
                })
        
        # Sort by similarity and limit results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
    
    async def delete_embedding(self, cache_key: str) -> bool:
        """Delete embedding from memory."""
        return self.embeddings.pop(cache_key, None) is not None
    
    async def delete_by_filter(self,
                             task_type: Optional[str] = None,
                             tenant_id: Optional[str] = None) -> int:
        """Delete embeddings by filter."""
        keys_to_delete = []
        
        for cache_key, (_, metadata) in self.embeddings.items():
            if task_type and metadata.get("task_type") != task_type:
                continue
            if tenant_id and metadata.get("tenant_id") != tenant_id:
                continue
            keys_to_delete.append(cache_key)
        
        for key in keys_to_delete:
            del self.embeddings[key]
        
        return len(keys_to_delete)
    
    async def delete_old_entries(self, cutoff_date: datetime) -> int:
        """Delete entries older than cutoff date."""
        keys_to_delete = []
        
        for cache_key, (_, metadata) in self.embeddings.items():
            created_at = datetime.fromisoformat(metadata["created_at"])
            if created_at < cutoff_date:
                keys_to_delete.append(cache_key)
        
        for key in keys_to_delete:
            del self.embeddings[key]
        
        return len(keys_to_delete)
    
    async def get_collection_size(self) -> int:
        """Get number of stored embeddings."""
        return len(self.embeddings)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return {
            "type": "memory",
            "size": len(self.embeddings),
            "memory_usage_mb": self._estimate_memory_usage()
        }
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        total_size = 0
        for embedding, _ in self.embeddings.values():
            total_size += embedding.nbytes
        
        return total_size / (1024 * 1024)


class WeaviateAdapter(VectorDBAdapter):
    """Weaviate vector database adapter."""
    
    def __init__(self,
                 url: str,
                 api_key: Optional[str] = None,
                 collection_name: str = "CacheEntries"):
        """Initialize Weaviate adapter."""
        if not WEAVIATE_AVAILABLE:
            raise ImportError("weaviate-client is required for WeaviateAdapter")
        
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.client: Optional[WeaviateClient] = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize Weaviate connection and schema."""
        auth_config = None
        if self.api_key:
            auth_config = weaviate.auth.AuthApiKey(api_key=self.api_key)
        
        self.client = weaviate.Client(
            url=self.url,
            auth_client_secret=auth_config
        )
        
        # Create collection if it doesn't exist
        await self._ensure_collection_exists()
        
        self.initialized = True
        logger.info(f"Weaviate adapter initialized with collection {self.collection_name}")
    
    async def _ensure_collection_exists(self):
        """Ensure the collection exists with proper schema."""
        # Check if collection exists
        try:
            self.client.schema.get(self.collection_name)
            logger.info(f"Collection {self.collection_name} already exists")
        except:
            # Create collection
            schema = {
                "class": self.collection_name,
                "description": "Semantic cache entries",
                "vectorizer": "none",  # We provide our own vectors
                "properties": [
                    {
                        "name": "cache_key",
                        "dataType": ["string"],
                        "description": "Unique cache key"
                    },
                    {
                        "name": "original_prompt",
                        "dataType": ["text"],
                        "description": "Original prompt text"
                    },
                    {
                        "name": "response",
                        "dataType": ["text"],
                        "description": "Cached response"
                    },
                    {
                        "name": "task_type",
                        "dataType": ["string"],
                        "description": "Task type"
                    },
                    {
                        "name": "model_id",
                        "dataType": ["string"],
                        "description": "Model ID"
                    },
                    {
                        "name": "created_at",
                        "dataType": ["date"],
                        "description": "Creation timestamp"
                    },
                    {
                        "name": "last_hit",
                        "dataType": ["date"],
                        "description": "Last hit timestamp"
                    },
                    {
                        "name": "hit_count",
                        "dataType": ["int"],
                        "description": "Number of hits"
                    },
                    {
                        "name": "expires_at",
                        "dataType": ["date"],
                        "description": "Expiration timestamp"
                    },
                    {
                        "name": "quality_score",
                        "dataType": ["number"],
                        "description": "Quality score"
                    },
                    {
                        "name": "cost_saved",
                        "dataType": ["number"],
                        "description": "Cost saved"
                    },
                    {
                        "name": "tenant_id",
                        "dataType": ["string"],
                        "description": "Tenant ID"
                    },
                    {
                        "name": "user_id",
                        "dataType": ["string"],
                        "description": "User ID"
                    }
                ]
            }
            
            self.client.schema.create_class(schema)
            logger.info(f"Created collection {self.collection_name}")
    
    async def store_embedding(self,
                            cache_key: str,
                            embedding: np.ndarray,
                            metadata: Dict[str, Any]) -> bool:
        """Store embedding in Weaviate."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        data_object = {
            "cache_key": cache_key,
            "original_prompt": metadata["original_prompt"],
            "response": metadata["response"],
            "task_type": metadata["task_type"],
            "model_id": metadata["model_id"],
            "created_at": metadata["created_at"],
            "last_hit": metadata.get("last_hit"),
            "hit_count": metadata["hit_count"],
            "expires_at": metadata.get("expires_at"),
            "quality_score": metadata["quality_score"],
            "cost_saved": metadata["cost_saved"],
            "tenant_id": metadata.get("tenant_id"),
            "user_id": metadata.get("user_id")
        }
        
        try:
            self.client.data_object.create(
                data_object=data_object,
                class_name=self.collection_name,
                vector=embedding.tolist()
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding in Weaviate: {e}")
            return False
    
    async def search_similar(self,
                          embedding: np.ndarray,
                          task_type: Optional[str] = None,
                          tenant_id: Optional[str] = None,
                          limit: int = 10,
                          similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar embeddings in Weaviate."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        # Build where clause
        where_clause = {}
        operands = []
        
        if task_type:
            operands.append({
                "path": ["task_type"],
                "operator": "Equal",
                "valueString": task_type
            })
        
        if tenant_id:
            operands.append({
                "path": ["tenant_id"],
                "operator": "Equal",
                "valueString": tenant_id
            })
        
        if len(operands) > 0:
            where_clause = {"operator": "And", "operands": operands}
        
        try:
            result = self.client.query.get(
                self.collection_name,
                ["cache_key", "original_prompt", "response", "task_type", "model_id",
                 "created_at", "last_hit", "hit_count", "expires_at", "quality_score",
                 "cost_saved", "tenant_id", "user_id"],
                vector=embedding.tolist(),
                limit=limit,
                certainty=similarity_threshold,  # Weaviate uses certainty = (1 + cosine) / 2
                where=where_clause if operands else None
            ).with_additional(["certainty", "id"]).do()
            
            results = []
            for item in result["data"]["Get"][self.collection_name]:
                # Convert Weaviate certainty back to cosine similarity
                certainty = item["_additional"]["certainty"]
                similarity = (certainty * 2) - 1
                
                results.append({
                    "cache_key": item["cache_key"],
                    "similarity": similarity,
                    "metadata": {
                        "original_prompt": item["original_prompt"],
                        "response": item["response"],
                        "task_type": item["task_type"],
                        "model_id": item["model_id"],
                        "created_at": item["created_at"],
                        "last_hit": item.get("last_hit"),
                        "hit_count": item["hit_count"],
                        "expires_at": item.get("expires_at"),
                        "quality_score": item["quality_score"],
                        "cost_saved": item["cost_saved"],
                        "tenant_id": item.get("tenant_id"),
                        "user_id": item.get("user_id")
                    }
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search Weaviate: {e}")
            return []
    
    async def delete_embedding(self, cache_key: str) -> bool:
        """Delete embedding by cache key."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        try:
            # Find object by cache_key
            where_clause = {
                "path": ["cache_key"],
                "operator": "Equal",
                "valueString": cache_key
            }
            
            result = self.client.query.get(
                self.collection_name,
                ["_id"],
                where=where_clause
            ).do()
            
            objects = result["data"]["Get"][self.collection_name]
            if objects:
                object_id = objects[0]["_id"]
                self.client.data_object.delete(
                    object_id,
                    class_name=self.collection_name
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete embedding from Weaviate: {e}")
            return False
    
    async def delete_by_filter(self,
                             task_type: Optional[str] = None,
                             tenant_id: Optional[str] = None) -> int:
        """Delete embeddings by filter."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        operands = []
        
        if task_type:
            operands.append({
                "path": ["task_type"],
                "operator": "Equal",
                "valueString": task_type
            })
        
        if tenant_id:
            operands.append({
                "path": ["tenant_id"],
                "operator": "Equal",
                "valueString": tenant_id
            })
        
        if not operands:
            return 0
        
        where_clause = {"operator": "And", "operands": operands}
        
        try:
            # Get all objects matching filter
            result = self.client.query.get(
                self.collection_name,
                ["_id"],
                where=where_clause
            ).do()
            
            objects = result["data"]["Get"][self.collection_name]
            deleted_count = 0
            
            for obj in objects:
                self.client.data_object.delete(
                    obj["_id"],
                    class_name=self.collection_name
                )
                deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete by filter from Weaviate: {e}")
            return 0
    
    async def delete_old_entries(self, cutoff_date: datetime) -> int:
        """Delete entries older than cutoff date."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        where_clause = {
            "path": ["created_at"],
            "operator": "LessThan",
            "valueDate": cutoff_date.isoformat() + "Z"
        }
        
        try:
            # Get all old objects
            result = self.client.query.get(
                self.collection_name,
                ["_id"],
                where=where_clause
            ).do()
            
            objects = result["data"]["Get"][self.collection_name]
            deleted_count = 0
            
            for obj in objects:
                self.client.data_object.delete(
                    obj["_id"],
                    class_name=self.collection_name
                )
                deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete old entries from Weaviate: {e}")
            return 0
    
    async def get_collection_size(self) -> int:
        """Get collection size."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        try:
            result = self.client.query.aggregate(self.collection_name).do()
            return result["data"]["Aggregate"][self.collection_name][0]["meta"]["count"]
        except Exception as e:
            logger.error(f"Failed to get collection size from Weaviate: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Weaviate statistics."""
        if not self.client:
            raise RuntimeError("Weaviate client not initialized")
        
        try:
            size = await self.get_collection_size()
            
            return {
                "type": "weaviate",
                "collection": self.collection_name,
                "size": size,
                "url": self.url
            }
        except Exception as e:
            logger.error(f"Failed to get Weaviate stats: {e}")
            return {"type": "weaviate", "error": str(e)}


class PineconeAdapter(VectorDBAdapter):
    """Pinecone vector database adapter."""
    
    def __init__(self,
                 api_key: str,
                 environment: str,
                 index_name: str = "semantic-cache",
                 dimension: int = 384):
        """Initialize Pinecone adapter."""
        if not PINECONE_AVAILABLE:
            raise ImportError("pinecone-client is required for PineconeAdapter")
        
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self.dimension = dimension
        self.pinecone: Optional[Pinecone] = None
        self.index = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize Pinecone connection and index."""
        self.pinecone = Pinecone(api_key=self.api_key)
        
        # Check if index exists
        if self.index_name not in self.pinecone.list_indexes().names():
            # Create index
            self.pinecone.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine"
            )
        
        self.index = self.pinecone.Index(self.index_name)
        self.initialized = True
        
        logger.info(f"Pinecone adapter initialized with index {self.index_name}")
    
    async def store_embedding(self,
                            cache_key: str,
                            embedding: np.ndarray,
                            metadata: Dict[str, Any]) -> bool:
        """Store embedding in Pinecone."""
        if not self.index:
            raise RuntimeError("Pinecone index not initialized")
        
        try:
            self.index.upsert(
                vectors=[{
                    "id": cache_key,
                    "values": embedding.tolist(),
                    "metadata": metadata
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store embedding in Pinecone: {e}")
            return False
    
    async def search_similar(self,
                          embedding: np.ndarray,
                          task_type: Optional[str] = None,
                          tenant_id: Optional[str] = None,
                          limit: int = 10,
                          similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar embeddings in Pinecone."""
        if not self.index:
            raise RuntimeError("Pinecone index not initialized")
        
        # Build filter
        filter_dict = {}
        if task_type:
            filter_dict["task_type"] = task_type
        if tenant_id:
            filter_dict["tenant_id"] = tenant_id
        
        try:
            result = self.index.query(
                vector=embedding.tolist(),
                top_k=limit,
                include_metadata=True,
                filter=filter_dict if filter_dict else None
            )
            
            results = []
            for match in result["matches"]:
                if match["score"] >= similarity_threshold:
                    results.append({
                        "cache_key": match["id"],
                        "similarity": match["score"],
                        "metadata": match["metadata"]
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            return []
    
    async def delete_embedding(self, cache_key: str) -> bool:
        """Delete embedding by cache key."""
        if not self.index:
            raise RuntimeError("Pinecone index not initialized")
        
        try:
            self.index.delete(ids=[cache_key])
            return True
        except Exception as e:
            logger.error(f"Failed to delete embedding from Pinecone: {e}")
            return False
    
    async def delete_by_filter(self,
                             task_type: Optional[str] = None,
                             tenant_id: Optional[str] = None) -> int:
        """Delete embeddings by filter."""
        # Pinecone doesn't support delete by filter directly
        # This would require fetching IDs first, then deleting
        # For now, return 0 as placeholder
        logger.warning("Pinecone delete_by_filter not fully implemented")
        return 0
    
    async def delete_old_entries(self, cutoff_date: datetime) -> int:
        """Delete entries older than cutoff date."""
        # Similar to delete_by_filter, this requires fetching first
        logger.warning("Pinecone delete_old_entries not fully implemented")
        return 0
    
    async def get_collection_size(self) -> int:
        """Get index size."""
        if not self.index:
            raise RuntimeError("Pinecone index not initialized")
        
        try:
            stats = self.index.describe_index_stats()
            return stats["total_vector_count"]
        except Exception as e:
            logger.error(f"Failed to get Pinecone index size: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Pinecone statistics."""
        if not self.index:
            raise RuntimeError("Pinecone index not initialized")
        
        try:
            stats = self.index.describe_index_stats()
            
            return {
                "type": "pinecone",
                "index": self.index_name,
                "dimension": self.dimension,
                "size": stats["total_vector_count"],
                "environment": self.environment
            }
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            return {"type": "pinecone", "error": str(e)}


def create_vector_adapter(db_type: str, **kwargs) -> VectorDBAdapter:
    """Factory function to create vector database adapter."""
    if db_type == VectorDBType.WEAVIATE:
        return WeaviateAdapter(**kwargs)
    elif db_type == VectorDBType.PINECONE:
        return PineconeAdapter(**kwargs)
    elif db_type == "memory":
        return MemoryVectorDB()
    else:
        raise ValueError(f"Unsupported vector database type: {db_type}")
