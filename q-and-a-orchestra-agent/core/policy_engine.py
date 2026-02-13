# core/policy_engine.py
from typing import List, Optional
from dataclasses import dataclass
import os
import logging

from .task_profiles import TaskProfile
from .model_registry import RegisteredModel, ModelRegistry
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ScoredModel:
    model: RegisteredModel
    score: float
    reasons: List[str]


class ModelPolicyEngine:
    def __init__(self, registry: ModelRegistry, policies_path: str = "config/policies.yaml"):
        self.registry = registry
        self.policies_path = Path(policies_path)
        self.policies = self._load_policies()

    def _load_policies(self) -> dict:
        """Load routing policies from YAML file."""
        try:
            with self.policies_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Policies file not found: {self.policies_path}, using defaults")
            return self._get_default_policies()
        except yaml.YAMLError as e:
            logger.error(f"Error parsing policies.yaml: {e}, using defaults")
            return self._get_default_policies()

    def _get_default_policies(self) -> dict:
        """Get default policies if config file is missing."""
        return {
            "routing": {
                "default_mode": "local-preferred",
                "modes": {
                    "local-only": {"allow_cloud": False},
                    "local-preferred": {"allow_cloud": True, "cloud_usage_strategy": "fallback_critical_only"},
                    "balanced": {"allow_cloud": True, "cloud_usage_strategy": "balanced"},
                    "performance": {"allow_cloud": True, "cloud_usage_strategy": "aggressive"}
                },
                "weights": {
                    "local-preferred": {"cost": 0.6, "quality": 0.25, "latency": 0.15},
                    "balanced": {"cost": 0.4, "quality": 0.4, "latency": 0.2},
                    "performance": {"cost": 0.2, "quality": 0.6, "latency": 0.2}
                }
            },
            "task_overrides": {},
            "budgets": {"daily": {"total_usd": 10.0}, "monthly": {"total_usd": 150.0}},
            "behavior_on_budget_exceeded": {"default": "downgrade_to_local"},
            "timeouts": {"default": 60, "high_latency_ok": 120, "low_latency_required": 15}
        }

    def _mode(self) -> str:
        """Get current routing mode from environment or config."""
        return os.getenv("MODEL_ROUTING_MODE", self.policies["routing"]["default_mode"])

    def _weights(self) -> dict:
        """Get scoring weights for current mode."""
        mode = self._mode()
        return self.policies["routing"]["weights"].get(mode, self.policies["routing"]["weights"]["local-preferred"])

    def select_candidates(self, task: TaskProfile) -> List[RegisteredModel]:
        """Select candidate models for a given task."""
        models = self.registry.models
        candidates: List[RegisteredModel] = []

        # Task-specific overrides
        overrides = self.policies.get("task_overrides", {}).get(task.task_type, {})
        preferred_caps = set(overrides.get("preferred_capabilities", []))
        preferred_providers = set(overrides.get("preferred_providers", []))

        for rm in models:
            cfg = rm.config

            # Check context size requirements
            if task.context_size and cfg.max_context < task.context_size:
                continue

            # Check capability requirements
            if (task.task_type not in cfg.capabilities and 
                not preferred_caps.intersection(cfg.capabilities)):
                continue

            # Check routing mode constraints
            mode = self._mode()
            allow_cloud = self.policies["routing"]["modes"][mode]["allow_cloud"]
            if not allow_cloud and rm.provider.type == "cloud":
                continue

            candidates.append(rm)

        # Prefer specific providers if specified
        if preferred_providers:
            prioritized = [c for c in candidates if c.provider_name in preferred_providers]
            if prioritized:
                return prioritized

        return candidates

    def score_model(self, rm: RegisteredModel, task: TaskProfile) -> ScoredModel:
        """Score a model for a given task."""
        w = self._weights()
        
        # Get cost (lower is better)
        cost = rm.config.cost_profile.relative_cost or 1.0
        
        # Quality rank mapping (lower is better)
        quality_rank_map = {"very_high": 1, "high": 2, "medium": 3, "low": 4}
        quality_rank = quality_rank_map.get(rm.config.quality_tier, 3)
        
        # Latency rank mapping (lower is better)
        latency_rank_map = {"low": 1, "medium": 2, "high": 3}
        latency_rank = latency_rank_map.get(rm.config.latency_tier, 2)

        # Calculate composite score (lower is better)
        score = (
            w["cost"] * cost +
            w["quality"] * quality_rank +
            w["latency"] * latency_rank
        )

        reasons = [
            f"cost={cost:.2f}",
            f"quality_rank={quality_rank}",
            f"latency_rank={latency_rank}",
        ]

        return ScoredModel(model=rm, score=score, reasons=reasons)

    def choose_best(self, task: TaskProfile) -> Optional[ScoredModel]:
        """Choose the best model for a given task."""
        candidates = self.select_candidates(task)
        if not candidates:
            logger.warning(f"No suitable models found for task: {task.task_type}")
            return None
        
        scored = [self.score_model(c, task) for c in candidates]
        scored.sort(key=lambda s: s.score)
        
        best = scored[0]
        logger.info(f"Selected model: {best.model.model_id} (provider: {best.model.provider_name}) "
                   f"with score {best.score:.3f} for task: {task.task_type}")
        
        return best
