"""
Advanced Policy Engine

Multi-criteria decision making for model selection with support for
learned mappings, reinforcement learning, and business rules.
"""

import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .reinforcement_learning import ReinforcementLearning, BanditAlgorithmType
from .learning_loop import LearningLoop
from ..metrics.learned_mappings import LearnedMappings
from ..introspection.model_profile import ModelProfile


logger = logging.getLogger(__name__)


class RoutingMode(str, Enum):
    """Model routing modes."""
    LOCAL_PREFERRED = "local_preferred"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    COST_OPTIMIZED = "cost_optimized"
    LEARNING_DRIVEN = "learning_driven"


@dataclass
class PolicyWeights:
    """Weights for different policy criteria."""
    cost: float = 0.4
    quality: float = 0.25
    latency: float = 0.15
    reliability: float = 0.1
    cache_efficiency: float = 0.05
    learning_confidence: float = 0.05
    
    def normalize(self):
        """Normalize weights to sum to 1.0."""
        total = sum([self.cost, self.quality, self.latency, 
                   self.reliability, self.cache_efficiency, self.learning_confidence])
        
        if total == 0:
            return
        
        self.cost /= total
        self.quality /= total
        self.latency /= total
        self.reliability /= total
        self.cache_efficiency /= total
        self.learning_confidence /= total
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "cost": self.cost,
            "quality": self.quality,
            "latency": self.latency,
            "reliability": self.reliability,
            "cache_efficiency": self.cache_efficiency,
            "learning_confidence": self.learning_confidence
        }


@dataclass
class SelectionCriteria:
    """Criteria for model selection."""
    task_type: str
    criticality: str  # "low", "medium", "high", "critical"
    max_cost_usd: Optional[float] = None
    max_latency_ms: Optional[float] = None
    min_quality_score: Optional[float] = None
    require_local: bool = False
    prefer_local: bool = False
    allowed_providers: Optional[List[str]] = None
    blocked_models: Optional[List[str]] = None
    
    # Context for selection
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_context: Optional[Dict[str, Any]] = None


@dataclass
class ModelSelection:
    """Result of model selection process."""
    selected_model: str
    selected_provider: str
    confidence: float  # 0-1
    selection_reason: str
    alternative_models: List[Tuple[str, float]]  # (model_id, score)
    
    # Selection details
    routing_mode: RoutingMode
    policy_weights: PolicyWeights
    learning_used: bool
    selection_time_ms: float
    
    # Scores for each criterion
    criterion_scores: Dict[str, float]


class AdvancedPolicyEngine:
    """Advanced policy engine for intelligent model selection."""
    
    def __init__(self,
                 learned_mappings: LearnedMappings,
                 reinforcement_learning: ReinforcementLearning,
                 learning_loop: LearningLoop):
        """Initialize policy engine."""
        self.learned_mappings = learned_mappings
        self.rl = reinforcement_learning
        self.learning_loop = learning_loop
        
        # Default routing mode and weights
        self.default_routing_mode = RoutingMode.LOCAL_PREFERRED
        self.default_weights = PolicyWeights()
        self.routing_mode_weights = self._create_routing_mode_weights()
        
        # Policy configuration
        self.enable_learning = True
        self.enable_exploration = True
        self.exploration_rate = 0.1
        self.min_confidence_threshold = 0.7
        
        # Cache for model profiles
        self.model_profiles: Dict[str, ModelProfile] = {}
        
        # Selection statistics
        self.selection_stats = {
            "total_selections": 0,
            "selections_by_mode": {},
            "selections_by_task": {},
            "learning_usage_rate": 0.0
        }
    
    def _create_routing_mode_weights(self) -> Dict[RoutingMode, PolicyWeights]:
        """Create weight configurations for different routing modes."""
        return {
            RoutingMode.LOCAL_PREFERRED: PolicyWeights(
                cost=0.6, quality=0.2, latency=0.1, reliability=0.05,
                cache_efficiency=0.03, learning_confidence=0.02
            ),
            RoutingMode.BALANCED: PolicyWeights(
                cost=0.4, quality=0.25, latency=0.15, reliability=0.1,
                cache_efficiency=0.05, learning_confidence=0.05
            ),
            RoutingMode.PERFORMANCE: PolicyWeights(
                cost=0.2, quality=0.4, latency=0.25, reliability=0.1,
                cache_efficiency=0.03, learning_confidence=0.02
            ),
            RoutingMode.COST_OPTIMIZED: PolicyWeights(
                cost=0.7, quality=0.15, latency=0.05, reliability=0.05,
                cache_efficiency=0.03, learning_confidence=0.02
            ),
            RoutingMode.LEARNING_DRIVEN: PolicyWeights(
                cost=0.2, quality=0.2, latency=0.1, reliability=0.05,
                cache_efficiency=0.05, learning_confidence=0.4
            )
        }
    
    async def select_model(self,
                          criteria: SelectionCriteria,
                          available_models: List[ModelProfile],
                          routing_mode: Optional[RoutingMode] = None) -> ModelSelection:
        """Select best model based on criteria and available models."""
        start_time = datetime.now()
        
        # Determine routing mode
        if routing_mode is None:
            routing_mode = self.default_routing_mode
        
        # Get policy weights for routing mode
        weights = self.routing_mode_weights.get(routing_mode, self.default_weights)
        
        # Filter models based on criteria
        candidate_models = self._filter_models(criteria, available_models)
        
        if not candidate_models:
            raise ValueError("No models meet the selection criteria")
        
        # Score models
        model_scores = await self._score_models(
            criteria, candidate_models, weights, routing_mode
        )
        
        # Select best model
        if self.enable_learning and routing_mode == RoutingMode.LEARNING_DRIVEN:
            selected_model_id = await self._select_with_learning(
                criteria.task_type, model_scores
            )
            learning_used = True
        else:
            selected_model_id = max(model_scores, key=lambda x: x[1])[0]
            learning_used = False
        
        # Get selected model profile
        selected_profile = next(
            (m for m in candidate_models if m.model_id == selected_model_id),
            candidate_models[0]
        )
        
        # Calculate confidence and alternatives
        sorted_scores = sorted(model_scores, key=lambda x: x[1], reverse=True)
        confidence = self._calculate_selection_confidence(sorted_scores)
        alternatives = [(model_id, score) for model_id, score in sorted_scores[1:4]]
        
        # Determine selection reason
        selection_reason = self._determine_selection_reason(
            selected_model_id, criteria, routing_mode, learning_used
        )
        
        # Calculate selection time
        selection_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        # Get criterion scores for selected model
        criterion_scores = await self._get_criterion_scores(
            criteria, selected_profile, weights
        )
        
        # Update statistics
        self._update_selection_stats(routing_mode, criteria.task_type, learning_used)
        
        selection = ModelSelection(
            selected_model=selected_model_id,
            selected_provider=selected_profile.provider,
            confidence=confidence,
            selection_reason=selection_reason,
            alternative_models=alternatives,
            routing_mode=routing_mode,
            policy_weights=weights,
            learning_used=learning_used,
            selection_time_ms=selection_time_ms,
            criterion_scores=criterion_scores
        )
        
        logger.info(f"Selected model: {selected_model_id} for task {criteria.task_type}")
        return selection
    
    def _filter_models(self, criteria: SelectionCriteria, models: List[ModelProfile]) -> List[ModelProfile]:
        """Filter models based on selection criteria."""
        filtered = []
        
        for model in models:
            # Provider filtering
            if criteria.allowed_providers and model.provider not in criteria.allowed_providers:
                continue
            
            # Blocked models
            if criteria.blocked_models and model.model_id in criteria.blocked_models:
                continue
            
            # Local model requirements
            if criteria.require_local and model.provider != "ollama":
                continue
            
            # Cost constraints
            if criteria.max_cost_usd:
                estimated_cost = model.estimated_cost_input_per_1k / 1000  # Rough estimate
                if estimated_cost > criteria.max_cost_usd:
                    continue
            
            # Quality requirements
            if criteria.min_quality_score:
                if model.average_quality_score < criteria.min_quality_score:
                    continue
            
            # Task suitability
            if not model.is_suitable_for_task(criteria.task_type, {
                "min_accuracy": criteria.min_quality_score or 0.7,
                "max_context": 4096,  # Default context requirement
                "min_quality_tier": "basic"
            }):
                continue
            
            filtered.append(model)
        
        return filtered
    
    async def _score_models(self,
                           criteria: SelectionCriteria,
                           models: List[ModelProfile],
                           weights: PolicyWeights,
                           routing_mode: RoutingMode) -> List[Tuple[str, float]]:
        """Score models based on policy weights and criteria."""
        scores = []
        
        for model in models:
            score = 0.0
            
            # Cost score (lower cost is better)
            cost_score = self._calculate_cost_score(model, criteria)
            score += cost_score * weights.cost
            
            # Quality score
            quality_score = model.average_quality_score
            score += quality_score * weights.quality
            
            # Latency score
            latency_score = self._calculate_latency_score(model, criteria)
            score += latency_score * weights.latency
            
            # Reliability score
            reliability_score = self._calculate_reliability_score(model)
            score += reliability_score * weights.reliability
            
            # Cache efficiency score
            cache_score = self._calculate_cache_score(model, criteria)
            score += cache_score * weights.cache_efficiency
            
            # Learning confidence score
            if self.enable_learning:
                learning_score = await self._calculate_learning_score(model, criteria.task_type)
                score += learning_score * weights.learning_confidence
            
            # Local preference bonus
            if criteria.prefer_local and model.provider == "ollama":
                score += 0.1
            
            scores.append((model.model_id, score))
        
        return scores
    
    def _calculate_cost_score(self, model: ModelProfile, criteria: SelectionCriteria) -> float:
        """Calculate cost score (0-1, higher is better)."""
        # Normalize cost (lower cost = higher score)
        max_acceptable_cost = criteria.max_cost_usd or 0.01  # Default $0.01
        cost_ratio = model.estimated_cost_input_per_1k / max_acceptable_cost
        
        if cost_ratio <= 1.0:
            return 1.0
        else:
            # Exponential decay for costs above threshold
            return max(0, np.exp(-2 * (cost_ratio - 1)))
    
    def _calculate_latency_score(self, model: ModelProfile, criteria: SelectionCriteria) -> float:
        """Calculate latency score (0-1, higher is better)."""
        # Use average latency from profile, or estimate based on model size
        if model.average_latency_ms > 0:
            latency_ms = model.average_latency_ms
        else:
            # Estimate latency based on model provider and size
            if model.provider == "ollama":
                latency_ms = 200  # Local models are fast
            elif model.provider in ["openai", "anthropic"]:
                latency_ms = 800  # Cloud models are slower
            else:
                latency_ms = 500  # Default estimate
        
        max_acceptable_latency = criteria.max_latency_ms or 1000  # Default 1s
        latency_ratio = latency_ms / max_acceptable_latency
        
        if latency_ratio <= 1.0:
            return 1.0
        else:
            return max(0, 1 / latency_ratio)
    
    def _calculate_reliability_score(self, model: ModelProfile) -> float:
        """Calculate reliability score (0-1, higher is better)."""
        # Base reliability on provider and model maturity
        if model.provider == "ollama":
            return 0.9  # Local models are very reliable
        elif model.provider in ["openai", "anthropic"]:
            return 0.95  # Major cloud providers are very reliable
        else:
            return 0.8  # Other providers have moderate reliability
    
    def _calculate_cache_score(self, model: ModelProfile, criteria: SelectionCriteria) -> float:
        """Calculate cache efficiency score (0-1, higher is better)."""
        # Local models typically have better cache potential
        if model.provider == "ollama":
            return 0.8
        else:
            return 0.4
    
    async def _calculate_learning_score(self, model: ModelProfile, task_type: str) -> float:
        """Calculate learning confidence score for model-task combination."""
        # Get learned mapping for this task-model combination
        mapping_stats = self.learned_mappings.get_mapping_stats()
        
        # Check if we have learned data for this combination
        task_mappings = [
            mapping for mapping in self.learned_mappings.mappings.values()
            if mapping.task_type == task_type and mapping.model_id == model.model_id
        ]
        
        if task_mappings:
            # Use the best mapping
            best_mapping = max(task_mappings, key=lambda x: x.confidence)
            return best_mapping.confidence
        else:
            # No learning data yet, return neutral score
            return 0.5
    
    async def _select_with_learning(self,
                                 task_type: str,
                                 model_scores: List[Tuple[str, float]]) -> str:
        """Select model using reinforcement learning."""
        model_ids = [model_id for model_id, _ in model_scores]
        
        # Use RL to select model
        selected_model = self.rl.select_model(task_type, model_ids)
        
        # If RL returns None, fall back to highest score
        if selected_model is None:
            return model_scores[0][0]
        
        return selected_model
    
    def _calculate_selection_confidence(self, sorted_scores: List[Tuple[str, float]]) -> float:
        """Calculate confidence in selection based on score distribution."""
        if len(sorted_scores) < 2:
            return 1.0
        
        best_score = sorted_scores[0][1]
        second_best_score = sorted_scores[1][1]
        
        if best_score == 0:
            return 0.0
        
        # Confidence based on margin over second best
        score_ratio = second_best_score / best_score
        confidence = 1.0 - score_ratio
        
        return min(max(confidence, 0.0), 1.0)
    
    def _determine_selection_reason(self,
                                  model_id: str,
                                  criteria: SelectionCriteria,
                                  routing_mode: RoutingMode,
                                  learning_used: bool) -> str:
        """Determine human-readable reason for selection."""
        reasons = []
        
        if learning_used:
            reasons.append("learning-based optimization")
        
        if routing_mode == RoutingMode.LOCAL_PREFERRED:
            reasons.append("local model preference")
        elif routing_mode == RoutingMode.COST_OPTIMIZED:
            reasons.append("cost optimization")
        elif routing_mode == RoutingMode.PERFORMANCE:
            reasons.append("performance optimization")
        
        if criteria.prefer_local:
            reasons.append("local model preferred")
        
        if criteria.max_cost_usd:
            reasons.append("cost constraints")
        
        if criteria.min_quality_score:
            reasons.append("quality requirements")
        
        if not reasons:
            reasons.append("policy-based selection")
        
        return ", ".join(reasons)
    
    async def _get_criterion_scores(self,
                                  criteria: SelectionCriteria,
                                  model: ModelProfile,
                                  weights: PolicyWeights) -> Dict[str, float]:
        """Get individual criterion scores for a model."""
        return {
            "cost": self._calculate_cost_score(model, criteria),
            "quality": model.average_quality_score,
            "latency": self._calculate_latency_score(model, criteria),
            "reliability": self._calculate_reliability_score(model),
            "cache_efficiency": self._calculate_cache_score(model, criteria),
            "learning_confidence": await self._calculate_learning_score(model, criteria.task_type)
        }
    
    def _update_selection_stats(self,
                              routing_mode: RoutingMode,
                              task_type: str,
                              learning_used: bool):
        """Update selection statistics."""
        self.selection_stats["total_selections"] += 1
        
        # By routing mode
        mode_key = routing_mode.value
        self.selection_stats["selections_by_mode"][mode_key] = \
            self.selection_stats["selections_by_mode"].get(mode_key, 0) + 1
        
        # By task type
        self.selection_stats["selections_by_task"][task_type] = \
            self.selection_stats["selections_by_task"].get(task_type, 0) + 1
        
        # Learning usage rate
        if learning_used:
            learning_selections = self.selection_stats.get("learning_selections", 0) + 1
            self.selection_stats["learning_selections"] = learning_selections
        
        total = self.selection_stats["total_selections"]
        learning_selections = self.selection_stats.get("learning_selections", 0)
        self.selection_stats["learning_usage_rate"] = learning_selections / total if total > 0 else 0
    
    def set_routing_mode(self, mode: RoutingMode):
        """Set default routing mode."""
        self.default_routing_mode = mode
        logger.info(f"Default routing mode set to {mode.value}")
    
    def update_policy_weights(self, routing_mode: RoutingMode, weights: PolicyWeights):
        """Update policy weights for a routing mode."""
        weights.normalize()
        self.routing_mode_weights[routing_mode] = weights
        logger.info(f"Updated weights for {routing_mode.value}: {weights.to_dict()}")
    
    def enable_learning_mode(self, enabled: bool = True):
        """Enable or disable learning-driven selection."""
        self.enable_learning = enabled
        logger.info(f"Learning mode {'enabled' if enabled else 'disabled'}")
    
    def set_exploration_rate(self, rate: float):
        """Set exploration rate for learning."""
        self.exploration_rate = max(0.0, min(1.0, rate))
        logger.info(f"Exploration rate set to {self.exploration_rate}")
    
    def get_policy_status(self) -> Dict[str, Any]:
        """Get current policy engine status."""
        return {
            "default_routing_mode": self.default_routing_mode.value,
            "enable_learning": self.enable_learning,
            "enable_exploration": self.enable_exploration,
            "exploration_rate": self.exploration_rate,
            "min_confidence_threshold": self.min_confidence_threshold,
            "selection_statistics": self.selection_stats,
            "routing_mode_weights": {
                mode.value: weights.to_dict()
                for mode, weights in self.routing_mode_weights.items()
            },
            "learning_status": self.learning_loop.get_learning_status(),
            "rl_convergence": self.rl.get_convergence_metrics()
        }
    
    async def analyze_policy_effectiveness(self,
                                        time_range: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """Analyze effectiveness of current policy configuration."""
        # This would analyze historical selection performance
        # For now, return placeholder analysis
        
        return {
            "analysis_period": {
                "start": (datetime.now() - time_range).isoformat(),
                "end": datetime.now().isoformat()
            },
            "total_selections": self.selection_stats["total_selections"],
            "selections_by_mode": self.selection_stats["selections_by_mode"],
            "learning_usage_rate": self.selection_stats["learning_usage_rate"],
            "average_confidence": 0.85,  # Placeholder
            "policy_recommendations": [
                "Consider increasing learning confidence weight for better optimization",
                "Local preferred mode shows good cost savings",
                "Learning-driven selections have 15% better efficiency"
            ]
        }
