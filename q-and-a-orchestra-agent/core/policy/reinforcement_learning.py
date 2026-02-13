"""
Reinforcement Learning

Implements bandit algorithms for model selection with Thompson sampling,
UCB1, epsilon-greedy, and contextual bandits.
"""

import asyncio
import logging
import numpy as np
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from ..metrics.learned_mappings import LearnedMapping


logger = logging.getLogger(__name__)


class BanditAlgorithmType(str, Enum):
    """Types of bandit algorithms."""
    THOMPSON_SAMPLING = "thompson_sampling"
    UCB1 = "ucb1"
    EPSILON_GREEDY = "epsilon_greedy"
    CONTEXTUAL_BANDIT = "contextual_bandit"


@dataclass
class BanditArm:
    """Represents an arm (model) in the bandit algorithm."""
    arm_id: str  # model_id
    task_type: str
    
    # Statistics
    pulls: int = 0
    rewards: List[float] = None
    total_reward: float = 0.0
    avg_reward: float = 0.0
    
    # Thompson sampling parameters (Beta distribution)
    alpha: float = 1.0  # Success parameter
    beta: float = 1.0   # Failure parameter
    
    # UCB1 parameters
    confidence_bound: float = 0.0
    
    # Context features (for contextual bandits)
    context_features: Dict[str, float] = None
    
    def __post_init__(self):
        if self.rewards is None:
            self.rewards = []
        if self.context_features is None:
            self.context_features = {}
    
    def update(self, reward: float):
        """Update arm statistics with new reward."""
        self.pulls += 1
        self.rewards.append(reward)
        self.total_reward += reward
        self.avg_reward = self.total_reward / self.pulls
        
        # Update Thompson sampling parameters
        if reward > 0.5:  # Success threshold
            self.alpha += 1
        else:
            self.beta += 1
    
    def get_thompson_sample(self) -> float:
        """Get Thompson sampling value from Beta distribution."""
        return np.random.beta(self.alpha, self.beta)
    
    def get_ucb1_value(self, total_pulls: int, exploration_factor: float = 2.0) -> float:
        """Get UCB1 value."""
        if self.pulls == 0:
            return float('inf')
        
        exploitation = self.avg_reward
        exploration = exploration_factor * np.sqrt(
            np.log(total_pulls) / self.pulls
        )
        
        return exploitation + exploration
    
    def get_variance(self) -> float:
        """Get reward variance."""
        if len(self.rewards) < 2:
            return 0.0
        
        return np.var(self.rewards)
    
    def get_confidence_interval(self, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for mean reward."""
        if len(self.rewards) < 2:
            return (0.0, 1.0)
        
        mean = self.avg_reward
        std_error = np.sqrt(self.get_variance() / self.pulls)
        
        # Normal approximation
        from scipy import stats
        margin = stats.t.ppf((1 + confidence) / 2, self.pulls - 1) * std_error
        
        return (mean - margin, mean + margin)


class BanditAlgorithm(ABC):
    """Abstract base class for bandit algorithms."""
    
    @abstractmethod
    def select_arm(self, arms: List[BanditArm], context: Optional[Dict[str, float]] = None) -> str:
        """Select an arm based on current statistics."""
        pass
    
    @abstractmethod
    def update_arm(self, arm: BanditArm, reward: float):
        """Update arm statistics with reward."""
        pass


class ThompsonSamplingBandit(BanditAlgorithm):
    """Thompson sampling bandit algorithm."""
    
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        """Initialize Thompson sampling with priors."""
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
    
    def select_arm(self, arms: List[BanditArm], context: Optional[Dict[str, float]] = None) -> str:
        """Select arm using Thompson sampling."""
        if not arms:
            raise ValueError("No arms available")
        
        # Sample from each arm's Beta distribution
        samples = [(arm.arm_id, arm.get_thompson_sample()) for arm in arms]
        
        # Select arm with highest sample
        best_arm_id = max(samples, key=lambda x: x[1])[0]
        return best_arm_id
    
    def update_arm(self, arm: BanditArm, reward: float):
        """Update arm with reward."""
        arm.update(reward)


class UCB1Bandit(BanditAlgorithm):
    """UCB1 bandit algorithm."""
    
    def __init__(self, exploration_factor: float = 2.0):
        """Initialize UCB1 with exploration factor."""
        self.exploration_factor = exploration_factor
    
    def select_arm(self, arms: List[BanditArm], context: Optional[Dict[str, float]] = None) -> str:
        """Select arm using UCB1."""
        if not arms:
            raise ValueError("No arms available")
        
        total_pulls = sum(arm.pulls for arm in arms)
        
        # Calculate UCB1 values
        ucb_values = [
            (arm.arm_id, arm.get_ucb1_value(total_pulls, self.exploration_factor))
            for arm in arms
        ]
        
        # Select arm with highest UCB1 value
        best_arm_id = max(ucb_values, key=lambda x: x[1])[0]
        return best_arm_id
    
    def update_arm(self, arm: BanditArm, reward: float):
        """Update arm with reward."""
        arm.update(reward)


class EpsilonGreedyBandit(BanditAlgorithm):
    """Epsilon-greedy bandit algorithm."""
    
    def __init__(self, epsilon: float = 0.1, decay_rate: float = 0.999):
        """Initialize epsilon-greedy with exploration rate."""
        self.epsilon = epsilon
        self.decay_rate = decay_rate
        self.current_epsilon = epsilon
    
    def select_arm(self, arms: List[BanditArm], context: Optional[Dict[str, float]] = None) -> str:
        """Select arm using epsilon-greedy."""
        if not arms:
            raise ValueError("No arms available")
        
        import random
        
        if random.random() < self.current_epsilon:
            # Explore: random selection
            return random.choice(arms).arm_id
        else:
            # Exploit: best known
            best_arm = max(arms, key=lambda x: x.avg_reward)
            return best_arm.arm_id
    
    def update_arm(self, arm: BanditArm, reward: float):
        """Update arm with reward."""
        arm.update(reward)
        
        # Decay epsilon
        self.current_epsilon *= self.decay_rate
        self.current_epsilon = max(self.current_epsilon, 0.01)  # Minimum epsilon


class ContextualBandit(BanditAlgorithm):
    """Contextual bandit using linear regression."""
    
    def __init__(self, learning_rate: float = 0.1, regularization: float = 0.01):
        """Initialize contextual bandit."""
        self.learning_rate = learning_rate
        self.regularization = regularization
        self.feature_weights: Dict[str, np.ndarray] = {}  # arm_id -> weights
    
    def select_arm(self, arms: List[BanditArm], context: Optional[Dict[str, float]] = None) -> str:
        """Select arm using contextual features."""
        if not arms:
            raise ValueError("No arms available")
        
        if not context:
            # Fall back to average reward if no context
            best_arm = max(arms, key=lambda x: x.avg_reward)
            return best_arm.arm_id
        
        # Calculate predicted rewards for each arm
        predictions = []
        for arm in arms:
            if arm.arm_id not in self.feature_weights:
                # Initialize weights for new arm
                self.feature_weights[arm.arm_id] = np.zeros(len(context))
            
            weights = self.feature_weights[arm.arm_id]
            features = np.array(list(context.values()))
            
            # Ensure dimensions match
            if len(weights) != len(features):
                weights = np.zeros(len(features))
                self.feature_weights[arm.arm_id] = weights
            
            predicted_reward = np.dot(weights, features)
            predictions.append((arm.arm_id, predicted_reward))
        
        # Select arm with highest predicted reward
        best_arm_id = max(predictions, key=lambda x: x[1])[0]
        return best_arm_id
    
    def update_arm(self, arm: BanditArm, reward: float, context: Optional[Dict[str, float]] = None):
        """Update arm with reward and context."""
        arm.update(reward)
        
        if context and arm.arm_id in self.feature_weights:
            # Update weights using gradient descent
            features = np.array(list(context.values()))
            weights = self.feature_weights[arm.arm_id]
            
            # Ensure dimensions match
            if len(weights) != len(features):
                weights = np.zeros(len(features))
                self.feature_weights[arm.arm_id] = weights
            
            # Calculate prediction error
            prediction = np.dot(weights, features)
            error = reward - prediction
            
            # Update weights with L2 regularization
            gradient = -2 * error * features + 2 * self.regularization * weights
            self.feature_weights[arm.arm_id] = weights - self.learning_rate * gradient


class ReinforcementLearning:
    """Reinforcement learning manager for model selection."""
    
    def __init__(self, algorithm_type: BanditAlgorithmType = BanditAlgorithmType.THOMPSON_SAMPLING):
        """Initialize RL manager."""
        self.algorithm_type = algorithm_type
        self.algorithm = self._create_algorithm(algorithm_type)
        self.arms: Dict[str, BanditArm] = {}  # task_type:model_id -> BanditArm
        self.context_history: List[Tuple[str, str, Dict[str, float]]] = []  # (task, model, context)
        self.reward_history: List[Tuple[str, str, float, datetime]] = []  # (task, model, reward, timestamp)
    
    def _create_algorithm(self, algorithm_type: BanditAlgorithmType) -> BanditAlgorithm:
        """Create bandit algorithm instance."""
        if algorithm_type == BanditAlgorithmType.THOMPSON_SAMPLING:
            return ThompsonSamplingBandit()
        elif algorithm_type == BanditAlgorithmType.UCB1:
            return UCB1Bandit()
        elif algorithm_type == BanditAlgorithmType.EPSILON_GREEDY:
            return EpsilonGreedyBandit()
        elif algorithm_type == BanditAlgorithmType.CONTEXTUAL_BANDIT:
            return ContextualBandit()
        else:
            raise ValueError(f"Unknown algorithm type: {algorithm_type}")
    
    def add_arm(self, task_type: str, model_id: str, initial_stats: Optional[Dict[str, float]] = None):
        """Add a new arm (model-task combination)."""
        arm_key = f"{task_type}:{model_id}"
        
        if arm_key in self.arms:
            logger.warning(f"Arm {arm_key} already exists")
            return
        
        arm = BanditArm(arm_id=model_id, task_type=task_type)
        
        # Initialize with prior statistics if provided
        if initial_stats:
            arm.pulls = int(initial_stats.get("pulls", 0))
            arm.avg_reward = initial_stats.get("avg_reward", 0.0)
            arm.total_reward = arm.avg_reward * arm.pulls
            
            # Set Thompson sampling priors based on initial stats
            if arm.pulls > 0:
                success_rate = arm.avg_reward
                arm.alpha = 1 + int(arm.pulls * success_rate)
                arm.beta = 1 + int(arm.pulls * (1 - success_rate))
        
        self.arms[arm_key] = arm
        logger.info(f"Added arm {arm_key}")
    
    def select_model(self, 
                   task_type: str, 
                   candidate_models: List[str],
                   context: Optional[Dict[str, float]] = None) -> Optional[str]:
        """Select best model for a task using RL algorithm."""
        # Get available arms for this task
        task_arms = [
            arm for arm in self.arms.values()
            if arm.task_type == task_type and arm.arm_id in candidate_models
        ]
        
        if not task_arms:
            logger.warning(f"No arms available for task {task_type}")
            return None
        
        # Select arm using algorithm
        selected_model_id = self.algorithm.select_arm(task_arms, context)
        
        # Store context for learning
        if context:
            self.context_history.append((task_type, selected_model_id, context))
        
        return selected_model_id
    
    def update_reward(self,
                     task_type: str,
                     model_id: str,
                     reward: float,
                     context: Optional[Dict[str, float]] = None):
        """Update algorithm with reward feedback."""
        arm_key = f"{task_type}:{model_id}"
        
        if arm_key not in self.arms:
            logger.warning(f"Arm {arm_key} not found for reward update")
            return
        
        arm = self.arms[arm_key]
        
        # Update arm using algorithm
        if isinstance(self.algorithm, ContextualBandit):
            self.algorithm.update_arm(arm, reward, context)
        else:
            self.algorithm.update_arm(arm, reward)
        
        # Store reward history
        self.reward_history.append((task_type, model_id, reward, datetime.now()))
        
        logger.debug(f"Updated reward for {arm_key}: {reward}")
    
    def get_arm_statistics(self, task_type: str, model_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific arm."""
        arm_key = f"{task_type}:{model_id}"
        
        if arm_key not in self.arms:
            return None
        
        arm = self.arms[arm_key]
        
        stats = {
            "arm_id": arm.arm_id,
            "task_type": arm.task_type,
            "pulls": arm.pulls,
            "avg_reward": arm.avg_reward,
            "total_reward": arm.total_reward,
            "alpha": arm.alpha,
            "beta": arm.beta,
            "confidence_interval": arm.get_confidence_interval(),
            "variance": arm.get_variance()
        }
        
        return stats
    
    def get_task_statistics(self, task_type: str) -> List[Dict[str, Any]]:
        """Get statistics for all arms of a task."""
        task_arms = [
            self.get_arm_statistics(arm.task_type, arm.arm_id)
            for arm in self.arms.values()
            if arm.task_type == task_type
        ]
        
        return [stats for stats in task_arms if stats is not None]
    
    def get_exploration_rate(self) -> float:
        """Get current exploration rate."""
        if isinstance(self.algorithm, EpsilonGreedyBandit):
            return self.algorithm.current_epsilon
        else:
            # For other algorithms, estimate exploration from variance
            if not self.arms:
                return 0.0
            
            avg_variance = np.mean([arm.get_variance() for arm in self.arms.values()])
            return min(avg_variance, 1.0)
    
    def get_convergence_metrics(self) -> Dict[str, Any]:
        """Get convergence metrics for the learning algorithm."""
        if not self.arms:
            return {"total_arms": 0}
        
        # Calculate convergence metrics
        total_pulls = sum(arm.pulls for arm in self.arms.values())
        avg_pulls_per_arm = total_pulls / len(self.arms)
        
        # Calculate reward variance across arms
        rewards = [arm.avg_reward for arm in self.arms.values() if arm.pulls > 0]
        reward_variance = np.var(rewards) if rewards else 0.0
        
        # Calculate confidence in best arm
        best_arms = {}
        for task_type in set(arm.task_type for arm in self.arms.values()):
            task_arms = [arm for arm in self.arms.values() if arm.task_type == task_type]
            if task_arms:
                best_arm = max(task_arms, key=lambda x: x.avg_reward)
                confidence = min(best_arm.pulls / 100, 1.0)  # Confidence based on pulls
                best_arms[task_type] = {
                    "model_id": best_arm.arm_id,
                    "confidence": confidence,
                    "pulls": best_arm.pulls
                }
        
        return {
            "total_arms": len(self.arms),
            "total_pulls": total_pulls,
            "avg_pulls_per_arm": avg_pulls_per_arm,
            "reward_variance": reward_variance,
            "exploration_rate": self.get_exploration_rate(),
            "best_arms_by_task": best_arms,
            "algorithm_type": self.algorithm_type.value
        }
    
    def export_state(self) -> Dict[str, Any]:
        """Export algorithm state for backup."""
        export_data = {
            "algorithm_type": self.algorithm_type.value,
            "arms": {},
            "context_history": self.context_history[-1000:],  # Last 1000 contexts
            "reward_history": [(task, model, reward, ts.isoformat()) 
                              for task, model, reward, ts in self.reward_history[-1000:]]
        }
        
        for arm_key, arm in self.arms.items():
            export_data["arms"][arm_key] = {
                "arm_id": arm.arm_id,
                "task_type": arm.task_type,
                "pulls": arm.pulls,
                "rewards": arm.rewards[-100:],  # Last 100 rewards
                "total_reward": arm.total_reward,
                "avg_reward": arm.avg_reward,
                "alpha": arm.alpha,
                "beta": arm.beta,
                "context_features": arm.context_features
            }
        
        return export_data
    
    def import_state(self, export_data: Dict[str, Any]):
        """Import algorithm state from backup."""
        logger.info(f"Importing {len(export_data.get('arms', {}))} arms")
        
        # Clear existing state
        self.arms.clear()
        
        # Import arms
        for arm_key, arm_data in export_data.get("arms", {}).items():
            arm = BanditArm(
                arm_id=arm_data["arm_id"],
                task_type=arm_data["task_type"]
            )
            
            arm.pulls = arm_data["pulls"]
            arm.rewards = arm_data["rewards"]
            arm.total_reward = arm_data["total_reward"]
            arm.avg_reward = arm_data["avg_reward"]
            arm.alpha = arm_data["alpha"]
            arm.beta = arm_data["beta"]
            arm.context_features = arm_data.get("context_features", {})
            
            self.arms[arm_key] = arm
        
        # Import history (limited)
        self.context_history = export_data.get("context_history", [])
        
        reward_history = export_data.get("reward_history", [])
        self.reward_history = [
            (task, model, reward, datetime.fromisoformat(ts))
            for task, model, reward, ts in reward_history
        ]
        
        logger.info("State import completed")
