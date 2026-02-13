"""
Learning Loop

Collects feedback and manages the continuous learning loop for
model selection optimization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .reinforcement_learning import ReinforcementLearning
from ..metrics.request_telemetry import RequestMetrics


logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of feedback for learning."""
    EXPLICIT = "explicit"  # User-provided feedback
    IMPLICIT = "implicit"  # Inferred from behavior
    PERFORMANCE = "performance"  # Based on metrics
    COST = "cost"  # Cost-based feedback


@dataclass
class FeedbackSignal:
    """Feedback signal for learning."""
    request_id: str
    task_type: str
    model_id: str
    feedback_type: FeedbackType
    
    # Feedback content
    reward: float  # 0-1 normalized reward
    confidence: float  # 0-1 confidence in feedback
    
    # Context
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = None
    
    # Additional metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LearningMetrics:
    """Metrics for learning performance."""
    total_feedback_signals: int
    feedback_by_type: Dict[str, int]
    average_reward: float
    reward_trend: str  # "improving", "stable", "declining"
    convergence_score: float  # 0-1
    last_update: datetime
    
    # Task-specific metrics
    task_performance: Dict[str, Dict[str, float]]


class RewardCalculator:
    """Calculates rewards from request metrics and feedback."""
    
    def __init__(self):
        """Initialize reward calculator with default weights."""
        self.weights = {
            "quality": 0.3,
            "latency": 0.25,
            "cost": 0.2,
            "success": 0.15,
            "cache_efficiency": 0.1
        }
        
        # Normalization parameters
        self.target_latency_ms = 500.0
        self.target_cost_usd = 0.01
        self.min_quality_score = 0.6
    
    def calculate_reward(self, metrics: RequestMetrics) -> float:
        """Calculate reward from request metrics."""
        # Quality component
        quality_score = metrics.quality.overall_score
        quality_reward = max(0, quality_score - self.min_quality_score) / (1 - self.min_quality_score)
        
        # Latency component (lower is better)
        latency_score = min(self.target_latency_ms / max(metrics.timing.total_latency_ms, 1), 1.0)
        
        # Cost component (lower is better)
        cost_score = min(self.target_cost_usd / max(metrics.cost_usd, 0.0001), 1.0)
        
        # Success component
        success_reward = 1.0 if metrics.success else 0.0
        
        # Cache efficiency component
        cache_reward = metrics.cache.get_cache_efficiency_score()
        
        # Calculate weighted reward
        reward = (
            quality_reward * self.weights["quality"] +
            latency_score * self.weights["latency"] +
            cost_score * self.weights["cost"] +
            success_reward * self.weights["success"] +
            cache_reward * self.weights["cache_efficiency"]
        )
        
        return min(max(reward, 0.0), 1.0)
    
    def calculate_explicit_reward(self,
                                 user_rating: float,
                                 metrics: RequestMetrics) -> float:
        """Calculate reward from explicit user feedback."""
        # User rating is primary signal (0-1)
        user_weight = 0.7
        performance_weight = 0.3
        
        performance_reward = self.calculate_reward(metrics)
        
        combined_reward = user_rating * user_weight + performance_reward * performance_weight
        return min(max(combined_reward, 0.0), 1.0)
    
    def calculate_cost_reward(self, metrics: RequestMetrics) -> float:
        """Calculate reward based primarily on cost efficiency."""
        cost_weights = {
            "cost": 0.5,
            "cache_efficiency": 0.3,
            "latency": 0.2
        }
        
        # Cost component
        cost_score = min(self.target_cost_usd / max(metrics.cost_usd, 0.0001), 1.0)
        
        # Cache efficiency
        cache_reward = metrics.cache.get_cache_efficiency_score()
        
        # Latency
        latency_score = min(self.target_latency_ms / max(metrics.timing.total_latency_ms, 1), 1.0)
        
        reward = (
            cost_score * cost_weights["cost"] +
            cache_reward * cost_weights["cache_efficiency"] +
            latency_score * cost_weights["latency"]
        )
        
        return min(max(reward, 0.0), 1.0)
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update reward calculation weights."""
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total_weight}, normalizing to 1.0")
            # Normalize weights
            new_weights = {k: v / total_weight for k, v in new_weights.items()}
        
        self.weights.update(new_weights)
        logger.info(f"Updated reward weights: {self.weights}")


class FeedbackCollector:
    """Collects and manages feedback signals."""
    
    def __init__(self):
        """Initialize feedback collector."""
        self.feedback_buffer: List[FeedbackSignal] = []
        self.buffer_size = 1000
        self.collection_rules = self._default_collection_rules()
    
    def _default_collection_rules(self) -> Dict[str, Any]:
        """Default rules for feedback collection."""
        return {
            "auto_collect_performance": True,
            "auto_collect_cost": True,
            "min_confidence_threshold": 0.5,
            "max_feedback_age_hours": 24,
            "feedback_types": {
                "explicit": {"enabled": True, "weight": 1.0},
                "implicit": {"enabled": True, "weight": 0.8},
                "performance": {"enabled": True, "weight": 0.9},
                "cost": {"enabled": True, "weight": 0.7}
            }
        }
    
    async def collect_feedback_from_metrics(self, metrics: RequestMetrics) -> List[FeedbackSignal]:
        """Collect feedback signals from request metrics."""
        signals = []
        
        # Performance feedback
        if self.collection_rules["auto_collect_performance"]:
            reward_calculator = RewardCalculator()
            reward = reward_calculator.calculate_reward(metrics)
            
            performance_signal = FeedbackSignal(
                request_id=metrics.request_id,
                task_type=metrics.task_type.value,
                model_id=metrics.selected_model_id,
                feedback_type=FeedbackType.PERFORMANCE,
                reward=reward,
                confidence=0.8,  # High confidence in performance metrics
                user_id=metrics.user_id,
                tenant_id=metrics.tenant_id,
                session_id=metrics.session_id,
                metadata={
                    "latency_ms": metrics.timing.total_latency_ms,
                    "cost_usd": metrics.cost_usd,
                    "quality_score": metrics.quality.overall_score,
                    "success": metrics.success
                }
            )
            signals.append(performance_signal)
        
        # Cost feedback
        if self.collection_rules["auto_collect_cost"]:
            reward_calculator = RewardCalculator()
            reward = reward_calculator.calculate_cost_reward(metrics)
            
            cost_signal = FeedbackSignal(
                request_id=metrics.request_id,
                task_type=metrics.task_type.value,
                model_id=metrics.selected_model_id,
                feedback_type=FeedbackType.COST,
                reward=reward,
                confidence=0.9,  # Very high confidence in cost calculations
                user_id=metrics.user_id,
                tenant_id=metrics.tenant_id,
                session_id=metrics.session_id,
                metadata={
                    "cost_usd": metrics.cost_usd,
                    "cache_hit": metrics.cache.cache_hit,
                    "cache_efficiency": metrics.cache.get_cache_efficiency_score()
                }
            )
            signals.append(cost_signal)
        
        return signals
    
    def add_explicit_feedback(self,
                            request_id: str,
                            task_type: str,
                            model_id: str,
                            user_rating: float,
                            user_id: Optional[str] = None,
                            tenant_id: Optional[str] = None,
                            comment: Optional[str] = None):
        """Add explicit user feedback."""
        signal = FeedbackSignal(
            request_id=request_id,
            task_type=task_type,
            model_id=model_id,
            feedback_type=FeedbackType.EXPLICIT,
            reward=user_rating,
            confidence=1.0,  # Maximum confidence for explicit feedback
            user_id=user_id,
            tenant_id=tenant_id,
            metadata={"comment": comment} if comment else {}
        )
        
        self._add_to_buffer(signal)
        logger.info(f"Added explicit feedback: {signal.reward} for {model_id}")
    
    def add_implicit_feedback(self,
                           request_id: str,
                           task_type: str,
                           model_id: str,
                           implicit_signals: Dict[str, float],
                           user_id: Optional[str] = None,
                           tenant_id: Optional[str] = None):
        """Add implicit feedback from user behavior."""
        # Calculate implicit reward from signals
        # Examples: time spent viewing response, whether user copied response, etc.
        view_time_score = implicit_signals.get("view_time_seconds", 0) / 30.0  # Normalize to 30s
        copy_score = 1.0 if implicit_signals.get("copied_response", False) else 0.0
        follow_up_score = implicit_signals.get("follow_up_requests", 0) / 5.0  # Normalize to 5 requests
        
        # Combine implicit signals
        implicit_reward = (
            view_time_score * 0.4 +
            copy_score * 0.4 +
            follow_up_score * 0.2
        )
        
        signal = FeedbackSignal(
            request_id=request_id,
            task_type=task_type,
            model_id=model_id,
            feedback_type=FeedbackType.IMPLICIT,
            reward=min(max(implicit_reward, 0.0), 1.0),
            confidence=0.6,  # Medium confidence for implicit feedback
            user_id=user_id,
            tenant_id=tenant_id,
            metadata=implicit_signals
        )
        
        self._add_to_buffer(signal)
    
    def _add_to_buffer(self, signal: FeedbackSignal):
        """Add signal to circular buffer."""
        self.feedback_buffer.append(signal)
        
        # Maintain buffer size
        if len(self.feedback_buffer) > self.buffer_size:
            self.feedback_buffer = self.feedback_buffer[-self.buffer_size:]
    
    def get_feedback_for_learning(self,
                               task_type: Optional[str] = None,
                               model_id: Optional[str] = None,
                               limit: int = 100) -> List[FeedbackSignal]:
        """Get feedback signals for learning."""
        filtered_signals = self.feedback_buffer
        
        # Apply filters
        if task_type:
            filtered_signals = [s for s in filtered_signals if s.task_type == task_type]
        
        if model_id:
            filtered_signals = [s for s in filtered_signals if s.model_id == model_id]
        
        # Sort by recency and limit
        filtered_signals.sort(key=lambda x: x.created_at, reverse=True)
        
        return filtered_signals[:limit]
    
    def get_feedback_statistics(self) -> Dict[str, Any]:
        """Get statistics about collected feedback."""
        if not self.feedback_buffer:
            return {"total_signals": 0}
        
        total_signals = len(self.feedback_buffer)
        
        # By type
        by_type = {}
        for signal in self.feedback_buffer:
            feedback_type = signal.feedback_type.value
            by_type[feedback_type] = by_type.get(feedback_type, 0) + 1
        
        # By task
        by_task = {}
        for signal in self.feedback_buffer:
            by_task[signal.task_type] = by_task.get(signal.task_type, 0) + 1
        
        # Average reward by type
        avg_reward_by_type = {}
        for signal in self.feedback_buffer:
            feedback_type = signal.feedback_type.value
            if feedback_type not in avg_reward_by_type:
                avg_reward_by_type[feedback_type] = []
            avg_reward_by_type[feedback_type].append(signal.reward)
        
        for feedback_type, rewards in avg_reward_by_type.items():
            avg_reward_by_type[feedback_type] = sum(rewards) / len(rewards)
        
        # Recent activity (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_signals = [s for s in self.feedback_buffer if s.created_at > one_hour_ago]
        
        return {
            "total_signals": total_signals,
            "by_type": by_type,
            "by_task": by_task,
            "avg_reward_by_type": avg_reward_by_type,
            "recent_signals_last_hour": len(recent_signals),
            "buffer_utilization": total_signals / self.buffer_size
        }


class LearningLoop:
    """Manages the continuous learning loop."""
    
    def __init__(self, 
                 reinforcement_learning: ReinforcementLearning,
                 feedback_collector: FeedbackCollector,
                 reward_calculator: RewardCalculator):
        """Initialize learning loop."""
        self.rl = reinforcement_learning
        self.feedback_collector = feedback_collector
        self.reward_calculator = reward_calculator
        
        self.learning_enabled = True
        self.learning_interval = timedelta(minutes=5)  # Learning every 5 minutes
        self.last_learning_time: Optional[datetime] = None
        
        # Learning metrics
        self.total_learning_iterations = 0
        self.last_learning_metrics: Optional[LearningMetrics] = None
    
    async def process_request_metrics(self, metrics: RequestMetrics):
        """Process request metrics and generate feedback."""
        if not self.learning_enabled:
            return
        
        # Collect feedback from metrics
        feedback_signals = await self.feedback_collector.collect_feedback_from_metrics(metrics)
        
        # Add feedback to buffer
        for signal in feedback_signals:
            self.feedback_collector._add_to_buffer(signal)
        
        # Update reinforcement learning with immediate feedback
        if feedback_signals:
            # Use the performance feedback for immediate RL update
            performance_signal = next(
                (s for s in feedback_signals if s.feedback_type == FeedbackType.PERFORMANCE),
                None
            )
            
            if performance_signal:
                self.rl.update_reward(
                    performance_signal.task_type,
                    performance_signal.model_id,
                    performance_signal.reward
                )
    
    async def add_explicit_feedback(self,
                                  request_id: str,
                                  task_type: str,
                                  model_id: str,
                                  user_rating: float,
                                  user_id: Optional[str] = None,
                                  tenant_id: Optional[str] = None,
                                  comment: Optional[str] = None):
        """Add explicit user feedback to learning loop."""
        if not self.learning_enabled:
            return
        
        self.feedback_collector.add_explicit_feedback(
            request_id, task_type, model_id, user_rating, user_id, tenant_id, comment
        )
        
        # Update RL immediately for explicit feedback
        self.rl.update_reward(task_type, model_id, user_rating)
    
    async def run_learning_iteration(self) -> LearningMetrics:
        """Run a learning iteration on accumulated feedback."""
        if not self.learning_enabled:
            raise RuntimeError("Learning is disabled")
        
        logger.info("Starting learning iteration")
        start_time = datetime.now()
        
        # Get recent feedback for learning
        feedback_signals = self.feedback_collector.get_feedback_for_learning(limit=500)
        
        if not feedback_signals:
            logger.warning("No feedback signals available for learning")
            return self._create_empty_metrics()
        
        # Group feedback by task-model combination
        grouped_feedback = {}
        for signal in feedback_signals:
            key = (signal.task_type, signal.model_id)
            if key not in grouped_feedback:
                grouped_feedback[key] = []
            grouped_feedback[key].append(signal)
        
        # Update RL with grouped feedback
        total_updates = 0
        total_reward = 0.0
        
        for (task_type, model_id), signals in grouped_feedback.items():
            # Calculate weighted average reward
            weighted_reward = 0.0
            total_weight = 0.0
            
            for signal in signals:
                weight = signal.confidence
                weighted_reward += signal.reward * weight
                total_weight += weight
            
            if total_weight > 0:
                avg_reward = weighted_reward / total_weight
                
                # Update RL
                self.rl.update_reward(task_type, model_id, avg_reward)
                
                total_updates += 1
                total_reward += avg_reward
        
        # Calculate learning metrics
        learning_metrics = self._calculate_learning_metrics(
            feedback_signals, total_updates, total_reward
        )
        
        self.last_learning_time = datetime.now()
        self.total_learning_iterations += 1
        self.last_learning_metrics = learning_metrics
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Learning iteration completed in {duration:.2f}s: {total_updates} updates")
        
        return learning_metrics
    
    def _calculate_learning_metrics(self,
                                  feedback_signals: List[FeedbackSignal],
                                  total_updates: int,
                                  total_reward: float) -> LearningMetrics:
        """Calculate metrics for the learning iteration."""
        # Basic metrics
        total_signals = len(feedback_signals)
        avg_reward = total_reward / total_updates if total_updates > 0 else 0.0
        
        # Feedback by type
        feedback_by_type = {}
        for signal in feedback_signals:
            feedback_type = signal.feedback_type.value
            feedback_by_type[feedback_type] = feedback_by_type.get(feedback_type, 0) + 1
        
        # Task-specific performance
        task_performance = {}
        task_rewards = {}
        task_counts = {}
        
        for signal in feedback_signals:
            task_type = signal.task_type
            if task_type not in task_rewards:
                task_rewards[task_type] = 0.0
                task_counts[task_type] = 0
            
            task_rewards[task_type] += signal.reward
            task_counts[task_type] += 1
        
        for task_type in task_rewards:
            task_performance[task_type] = {
                "avg_reward": task_rewards[task_type] / task_counts[task_type],
                "signal_count": task_counts[task_type]
            }
        
        # Convergence score (based on RL convergence metrics)
        convergence_metrics = self.rl.get_convergence_metrics()
        convergence_score = self._calculate_convergence_score(convergence_metrics)
        
        # Reward trend (simple trend analysis)
        reward_trend = self._calculate_reward_trend(feedback_signals)
        
        return LearningMetrics(
            total_feedback_signals=total_signals,
            feedback_by_type=feedback_by_type,
            average_reward=avg_reward,
            reward_trend=reward_trend,
            convergence_score=convergence_score,
            last_update=datetime.now(),
            task_performance=task_performance
        )
    
    def _calculate_convergence_score(self, convergence_metrics: Dict[str, Any]) -> float:
        """Calculate convergence score from RL metrics."""
        score = 0.0
        
        # High average pulls per arm contributes to convergence
        avg_pulls = convergence_metrics.get("avg_pulls_per_arm", 0)
        pulls_score = min(avg_pulls / 100, 1.0)  # Normalize to 100 pulls
        score += pulls_score * 0.4
        
        # Low exploration rate indicates convergence
        exploration_rate = convergence_metrics.get("exploration_rate", 1.0)
        exploration_score = max(0, 1 - exploration_rate)
        score += exploration_score * 0.3
        
        # Low reward variance indicates convergence
        reward_variance = convergence_metrics.get("reward_variance", 1.0)
        variance_score = max(0, 1 - reward_variance)
        score += variance_score * 0.3
        
        return min(max(score, 0.0), 1.0)
    
    def _calculate_reward_trend(self, feedback_signals: List[FeedbackSignal]) -> str:
        """Calculate reward trend over time."""
        if len(feedback_signals) < 10:
            return "stable"
        
        # Sort by time
        sorted_signals = sorted(feedback_signals, key=lambda x: x.created_at)
        
        # Split into two halves
        mid_point = len(sorted_signals) // 2
        early_signals = sorted_signals[:mid_point]
        recent_signals = sorted_signals[mid_point:]
        
        # Calculate average rewards
        early_avg = sum(s.reward for s in early_signals) / len(early_signals)
        recent_avg = sum(s.reward for s in recent_signals) / len(recent_signals)
        
        # Determine trend
        change_pct = ((recent_avg - early_avg) / early_avg) * 100 if early_avg > 0 else 0
        
        if change_pct > 5:
            return "improving"
        elif change_pct < -5:
            return "declining"
        else:
            return "stable"
    
    def _create_empty_metrics(self) -> LearningMetrics:
        """Create empty learning metrics."""
        return LearningMetrics(
            total_feedback_signals=0,
            feedback_by_type={},
            average_reward=0.0,
            reward_trend="stable",
            convergence_score=0.0,
            last_update=datetime.now(),
            task_performance={}
        )
    
    async def should_run_learning(self) -> bool:
        """Check if learning should run based on schedule and conditions."""
        if not self.learning_enabled:
            return False
        
        if self.last_learning_time is None:
            return True
        
        time_since_last = datetime.now() - self.last_learning_time
        return time_since_last >= self.learning_interval
    
    def get_learning_status(self) -> Dict[str, Any]:
        """Get current learning status."""
        feedback_stats = self.feedback_collector.get_feedback_statistics()
        convergence_metrics = self.rl.get_convergence_metrics()
        
        return {
            "learning_enabled": self.learning_enabled,
            "total_learning_iterations": self.total_learning_iterations,
            "last_learning_time": self.last_learning_time.isoformat() if self.last_learning_time else None,
            "learning_interval_minutes": self.learning_interval.total_seconds() / 60,
            "feedback_statistics": feedback_stats,
            "convergence_metrics": convergence_metrics,
            "last_learning_metrics": self.last_learning_metrics.__dict__ if self.last_learning_metrics else None
        }
    
    def enable_learning(self):
        """Enable learning loop."""
        self.learning_enabled = True
        logger.info("Learning loop enabled")
    
    def disable_learning(self):
        """Disable learning loop."""
        self.learning_enabled = False
        logger.info("Learning loop disabled")
    
    def set_learning_interval(self, interval: timedelta):
        """Set learning interval."""
        self.learning_interval = interval
        logger.info(f"Learning interval set to {interval}")
    
    async def force_learning_iteration(self) -> LearningMetrics:
        """Force a learning iteration regardless of schedule."""
        return await self.run_learning_iteration()
