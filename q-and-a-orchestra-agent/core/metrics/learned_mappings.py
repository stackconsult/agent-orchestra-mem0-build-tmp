"""
Learned Mappings

Machine learning-based model selection optimization that learns
from historical performance data to improve routing decisions.
"""

import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .telemetry_store import TelemetryStore


logger = logging.getLogger(__name__)


class LearningStrategy(str, Enum):
    """Learning strategy types."""
    THOMPSON_SAMPLING = "thompson_sampling"
    UCB1 = "ucb1"
    EPSILON_GREEDY = "epsilon_greedy"
    CONTEXTUAL_BANDIT = "contextual_bandit"


@dataclass
class LearnedMapping:
    """Learned mapping for task-model combinations."""
    task_type: str
    model_id: str
    provider: str
    
    # Performance metrics
    avg_latency_ms: float
    p95_latency_ms: float
    avg_quality_score: float
    avg_cost_usd: float
    success_rate: float
    cache_hit_rate: float
    
    # Calculated metrics
    efficiency_score: float
    rank_in_category: int
    
    # Learning metrics
    sample_count: int
    confidence: float  # 0-1
    last_trained: datetime
    
    # Bandit algorithm parameters
    alpha: float = 1.0  # Success parameter for Beta distribution
    beta: float = 1.0   # Failure parameter for Beta distribution
    reward_variance: float = 0.0
    
    def update_bandit_params(self, reward: float):
        """Update bandit algorithm parameters based on reward."""
        # For Thompson sampling with Beta distribution
        if reward > 0.5:  # Success
            self.alpha += 1
        else:  # Failure
            self.beta += 1
        
        # Update reward variance
        self.reward_variance = (self.alpha * self.beta) / (
            (self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1)
        )
    
    def get_thompson_sample(self) -> float:
        """Get Thompson sampling value."""
        return np.random.beta(self.alpha, self.beta)
    
    def get_ucb1_value(self, total_trials: int, exploration_factor: float = 2.0) -> float:
        """Get UCB1 value."""
        if self.sample_count == 0:
            return float('inf')
        
        exploitation = self.efficiency_score
        exploration = exploration_factor * np.sqrt(
            np.log(total_trials) / self.sample_count
        )
        
        return exploitation + exploration


class LearnedMappings:
    """Manages learned mappings for model selection optimization."""
    
    def __init__(self, telemetry_store: TelemetryStore):
        """Initialize learned mappings."""
        self.telemetry_store = telemetry_store
        self.mappings: Dict[str, LearnedMapping] = {}  # task_type:model_id -> LearnedMapping
        self.learning_strategy = LearningStrategy.THOMPSON_SAMPLING
        self.exploration_factor = 0.1  # For epsilon-greedy
        self.min_samples_for_learning = 10
        self.confidence_threshold = 0.7
        self.last_training_time: Optional[datetime] = None
    
    async def train_mappings(self, days: int = 30) -> Dict[str, Any]:
        """Train mappings from historical data."""
        logger.info(f"Training learned mappings from {days} days of data")
        
        start_time = datetime.now()
        time_range = timedelta(days=days)
        
        # Get all task types
        task_types = await self._get_task_types(time_range)
        
        # Train mappings for each task type
        for task_type in task_types:
            await self._train_task_mappings(task_type, time_range)
        
        # Calculate rankings and confidence scores
        await self._calculate_rankings()
        await self._update_confidence_scores()
        
        # Store mappings in database
        await self._store_mappings()
        
        self.last_training_time = datetime.now()
        
        training_stats = {
            "task_types_trained": len(task_types),
            "total_mappings": len(self.mappings),
            "training_duration_seconds": (datetime.now() - start_time).total_seconds(),
            "last_training_time": self.last_training_time.isoformat()
        }
        
        logger.info(f"Training completed: {training_stats}")
        return training_stats
    
    async def _get_task_types(self, time_range: timedelta) -> List[str]:
        """Get all task types from telemetry data."""
        # This would query the telemetry store for distinct task types
        # For now, return common task types
        return ["chat", "qa", "coding", "reasoning", "summarization", "creative"]
    
    async def _train_task_mappings(self, task_type: str, time_range: timedelta):
        """Train mappings for a specific task type."""
        # Get performance data for this task type
        task_performance = await self.telemetry_store.get_task_type_performance(
            task_type, time_range
        )
        
        for model_data in task_performance:
            model_id = model_data["model_id"]
            provider = model_data["provider"]
            mapping_key = f"{task_type}:{model_id}"
            
            # Calculate metrics
            avg_latency = model_data.get("avg_latency", 0)
            p95_latency = model_data.get("p95_latency", 0)
            avg_quality = model_data.get("avg_quality", 0)
            avg_cost = model_data.get("avg_cost", 0)
            success_rate = model_data.get("success_rate", 0)
            cache_hit_rate = model_data.get("cache_hit_rate", 0)
            sample_count = model_data.get("request_count", 0)
            
            # Skip if insufficient samples
            if sample_count < self.min_samples_for_learning:
                continue
            
            # Calculate efficiency score
            efficiency_score = self._calculate_efficiency_score(
                avg_latency, avg_cost, avg_quality, success_rate, cache_hit_rate
            )
            
            # Create or update mapping
            if mapping_key in self.mappings:
                mapping = self.mappings[mapping_key]
                # Update existing mapping with new data
                mapping.avg_latency_ms = avg_latency
                mapping.p95_latency_ms = p95_latency
                mapping.avg_quality_score = avg_quality
                mapping.avg_cost_usd = avg_cost
                mapping.success_rate = success_rate
                mapping.cache_hit_rate = cache_hit_rate
                mapping.efficiency_score = efficiency_score
                mapping.sample_count = sample_count
                mapping.last_trained = datetime.now()
            else:
                # Create new mapping
                mapping = LearnedMapping(
                    task_type=task_type,
                    model_id=model_id,
                    provider=provider,
                    avg_latency_ms=avg_latency,
                    p95_latency_ms=p95_latency,
                    avg_quality_score=avg_quality,
                    avg_cost_usd=avg_cost,
                    success_rate=success_rate,
                    cache_hit_rate=cache_hit_rate,
                    efficiency_score=efficiency_score,
                    rank_in_category=0,  # Will be calculated later
                    sample_count=sample_count,
                    confidence=0.0,  # Will be calculated later
                    last_trained=datetime.now()
                )
                self.mappings[mapping_key] = mapping
    
    def _calculate_efficiency_score(self,
                                 avg_latency: float,
                                 avg_cost: float,
                                 avg_quality: float,
                                 success_rate: float,
                                 cache_hit_rate: float) -> float:
        """Calculate efficiency score for a model-task combination."""
        # Weight factors
        speed_weight = 0.25
        cost_weight = 0.25
        quality_weight = 0.3
        reliability_weight = 0.15
        cache_weight = 0.05
        
        # Normalize metrics
        speed_score = min(1000 / max(avg_latency, 1), 1.0)
        cost_score = min(0.01 / max(avg_cost, 0.0001), 1.0)
        quality_score = avg_quality
        reliability_score = success_rate
        cache_score = cache_hit_rate
        
        efficiency = (
            speed_score * speed_weight +
            cost_score * cost_weight +
            quality_score * quality_weight +
            reliability_score * reliability_weight +
            cache_score * cache_weight
        )
        
        return min(max(efficiency, 0.0), 1.0)
    
    async def _calculate_rankings(self):
        """Calculate rankings within each task category."""
        # Group mappings by task type
        task_groups = {}
        for mapping in self.mappings.values():
            if mapping.task_type not in task_groups:
                task_groups[mapping.task_type] = []
            task_groups[mapping.task_type].append(mapping)
        
        # Sort and rank within each task type
        for task_type, mappings in task_groups.items():
            # Sort by efficiency score (descending)
            sorted_mappings = sorted(mappings, key=lambda x: x.efficiency_score, reverse=True)
            
            # Assign ranks
            for rank, mapping in enumerate(sorted_mappings, 1):
                mapping.rank_in_category = rank
    
    async def _update_confidence_scores(self):
        """Update confidence scores based on sample count and variance."""
        for mapping in self.mappings.values():
            # Confidence based on sample count and consistency
            sample_confidence = min(mapping.sample_count / 100, 1.0)  # More samples = higher confidence
            variance_confidence = max(0, 1 - mapping.reward_variance)  # Lower variance = higher confidence
            
            # Combine confidences
            mapping.confidence = (sample_confidence * 0.6 + variance_confidence * 0.4)
    
    async def _store_mappings(self):
        """Store learned mappings in database."""
        # This would store mappings in the telemetry store
        # For now, just log
        logger.info(f"Storing {len(self.mappings)} learned mappings")
    
    async def get_best_model_for_task(self,
                                    task_type: str,
                                    exploration: bool = True,
                                    candidate_models: Optional[List[str]] = None) -> Optional[str]:
        """Get best model for a task using learned mappings."""
        # Filter mappings for task type
        task_mappings = [
            mapping for mapping in self.mappings.values()
            if mapping.task_type == task_type
        ]
        
        # Filter by candidate models if provided
        if candidate_models:
            task_mappings = [
                mapping for mapping in task_mappings
                if mapping.model_id in candidate_models
            ]
        
        if not task_mappings:
            return None
        
        # Filter by confidence threshold
        confident_mappings = [
            mapping for mapping in task_mappings
            if mapping.confidence >= self.confidence_threshold
        ]
        
        # If no confident mappings, use all available
        mappings_to_use = confident_mappings if confident_mappings else task_mappings
        
        if exploration:
            return self._explore_selection(mappings_to_use)
        else:
            return self._exploit_selection(mappings_to_use)
    
    def _explore_selection(self, mappings: List[LearnedMapping]) -> str:
        """Select model using exploration strategy."""
        if self.learning_strategy == LearningStrategy.THOMPSON_SAMPLING:
            return self._thompson_sampling_selection(mappings)
        elif self.learning_strategy == LearningStrategy.UCB1:
            return self._ucb1_selection(mappings)
        elif self.learning_strategy == LearningStrategy.EPSILON_GREEDY:
            return self._epsilon_greedy_selection(mappings)
        else:
            # Default to Thompson sampling
            return self._thompson_sampling_selection(mappings)
    
    def _exploit_selection(self, mappings: List[LearnedMapping]) -> str:
        """Select model using exploitation (best known)."""
        if not mappings:
            raise ValueError("No mappings available")
        
        # Select mapping with highest efficiency score
        best_mapping = max(mappings, key=lambda x: x.efficiency_score)
        return best_mapping.model_id
    
    def _thompson_sampling_selection(self, mappings: List[LearnedMapping]) -> str:
        """Select model using Thompson sampling."""
        if not mappings:
            raise ValueError("No mappings available")
        
        # Sample from each mapping's Beta distribution
        samples = [(mapping.model_id, mapping.get_thompson_sample()) for mapping in mappings]
        
        # Select mapping with highest sample
        best_model_id = max(samples, key=lambda x: x[1])[0]
        return best_model_id
    
    def _ucb1_selection(self, mappings: List[LearnedMapping]) -> str:
        """Select model using UCB1 algorithm."""
        if not mappings:
            raise ValueError("No mappings available")
        
        total_trials = sum(mapping.sample_count for mapping in mappings)
        
        # Calculate UCB1 values
        ucb_values = [
            (mapping.model_id, mapping.get_ucb1_value(total_trials))
            for mapping in mappings
        ]
        
        # Select mapping with highest UCB1 value
        best_model_id = max(ucb_values, key=lambda x: x[1])[0]
        return best_model_id
    
    def _epsilon_greedy_selection(self, mappings: List[LearnedMapping]) -> str:
        """Select model using epsilon-greedy strategy."""
        if not mappings:
            raise ValueError("No mappings available")
        
        import random
        
        if random.random() < self.exploration_factor:
            # Explore: random selection
            return random.choice(mappings).model_id
        else:
            # Exploit: best known
            return self._exploit_selection(mappings)
    
    async def update_mapping_feedback(self,
                                    task_type: str,
                                    model_id: str,
                                    reward: float):
        """Update mapping based on feedback (reward)."""
        mapping_key = f"{task_type}:{model_id}"
        
        if mapping_key not in self.mappings:
            # Create new mapping if it doesn't exist
            self.mappings[mapping_key] = LearnedMapping(
                task_type=task_type,
                model_id=model_id,
                provider="unknown",
                avg_latency_ms=0,
                p95_latency_ms=0,
                avg_quality_score=0,
                avg_cost_usd=0,
                success_rate=0,
                cache_hit_rate=0,
                efficiency_score=0,
                rank_in_category=0,
                sample_count=0,
                confidence=0,
                last_trained=datetime.now()
            )
        
        # Update bandit parameters
        mapping = self.mappings[mapping_key]
        mapping.update_bandit_params(reward)
        mapping.sample_count += 1
        mapping.last_trained = datetime.now()
        
        logger.debug(f"Updated mapping {mapping_key} with reward {reward}")
    
    async def get_mapping_stats(self) -> Dict[str, Any]:
        """Get statistics about learned mappings."""
        if not self.mappings:
            return {"total_mappings": 0}
        
        # Calculate statistics
        total_mappings = len(self.mappings)
        task_types = len(set(mapping.task_type for mapping in self.mappings.values()))
        models = len(set(mapping.model_id for mapping in self.mappings.values()))
        
        avg_confidence = sum(mapping.confidence for mapping in self.mappings.values()) / total_mappings
        avg_efficiency = sum(mapping.efficiency_score for mapping in self.mappings.values()) / total_mappings
        total_samples = sum(mapping.sample_count for mapping in self.mappings.values())
        
        # Confidence distribution
        confidence_ranges = {"high": 0, "medium": 0, "low": 0}
        for mapping in self.mappings.values():
            if mapping.confidence >= 0.8:
                confidence_ranges["high"] += 1
            elif mapping.confidence >= 0.5:
                confidence_ranges["medium"] += 1
            else:
                confidence_ranges["low"] += 1
        
        return {
            "total_mappings": total_mappings,
            "task_types": task_types,
            "models": models,
            "avg_confidence": round(avg_confidence, 3),
            "avg_efficiency": round(avg_efficiency, 3),
            "total_samples": total_samples,
            "confidence_distribution": confidence_ranges,
            "learning_strategy": self.learning_strategy.value,
            "last_training_time": self.last_training_time.isoformat() if self.last_training_time else None
        }
    
    async def export_mappings(self) -> Dict[str, Any]:
        """Export learned mappings for backup or analysis."""
        exported = {
            "version": "2.0",
            "exported_at": datetime.now().isoformat(),
            "learning_strategy": self.learning_strategy.value,
            "confidence_threshold": self.confidence_threshold,
            "mappings": {}
        }
        
        for key, mapping in self.mappings.items():
            exported["mappings"][key] = {
                "task_type": mapping.task_type,
                "model_id": mapping.model_id,
                "provider": mapping.provider,
                "avg_latency_ms": mapping.avg_latency_ms,
                "p95_latency_ms": mapping.p95_latency_ms,
                "avg_quality_score": mapping.avg_quality_score,
                "avg_cost_usd": mapping.avg_cost_usd,
                "success_rate": mapping.success_rate,
                "cache_hit_rate": mapping.cache_hit_rate,
                "efficiency_score": mapping.efficiency_score,
                "rank_in_category": mapping.rank_in_category,
                "sample_count": mapping.sample_count,
                "confidence": mapping.confidence,
                "last_trained": mapping.last_trained.isoformat(),
                "alpha": mapping.alpha,
                "beta": mapping.beta,
                "reward_variance": mapping.reward_variance
            }
        
        return exported
    
    async def import_mappings(self, exported_data: Dict[str, Any]):
        """Import learned mappings from exported data."""
        logger.info(f"Importing {len(exported_data.get('mappings', {}))} mappings")
        
        for key, mapping_data in exported_data.get("mappings", {}).items():
            mapping = LearnedMapping(
                task_type=mapping_data["task_type"],
                model_id=mapping_data["model_id"],
                provider=mapping_data["provider"],
                avg_latency_ms=mapping_data["avg_latency_ms"],
                p95_latency_ms=mapping_data["p95_latency_ms"],
                avg_quality_score=mapping_data["avg_quality_score"],
                avg_cost_usd=mapping_data["avg_cost_usd"],
                success_rate=mapping_data["success_rate"],
                cache_hit_rate=mapping_data["cache_hit_rate"],
                efficiency_score=mapping_data["efficiency_score"],
                rank_in_category=mapping_data["rank_in_category"],
                sample_count=mapping_data["sample_count"],
                confidence=mapping_data["confidence"],
                last_trained=datetime.fromisoformat(mapping_data["last_trained"]),
                alpha=mapping_data.get("alpha", 1.0),
                beta=mapping_data.get("beta", 1.0),
                reward_variance=mapping_data.get("reward_variance", 0.0)
            )
            
            self.mappings[key] = mapping
        
        logger.info("Mapping import completed")
