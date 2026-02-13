# core/telemetry.py
from typing import Any, Optional
import logging
import time
from datetime import datetime, timedelta

from .task_profiles import TaskProfile
from .policy_engine import ScoredModel

logger = logging.getLogger(__name__)


class Telemetry:
    """Telemetry and cost tracking for model usage."""
    
    def __init__(self):
        self.usage_log = []
        self.cost_tracker = {}
        
    def record_plan(self, task: TaskProfile, choice: Optional[ScoredModel]) -> None:
        """Record a model selection plan (dry run)."""
        if choice:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "task_type": task.task_type,
                "provider": choice.model.provider_name,
                "model": choice.model.model_id,
                "score": choice.score,
                "reasons": choice.reasons,
                "dry_run": True
            }
            self.usage_log.append(log_entry)
            logger.info(f"Model plan recorded: {choice.model.model_id} for {task.task_type}")

    def before_invoke(self, task: TaskProfile, choice: ScoredModel) -> None:
        """Record before model invocation."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "task_type": task.task_type,
            "provider": choice.model.provider_name,
            "model": choice.model.model_id,
            "score": choice.score,
            "start_time": time.time(),
            "dry_run": False
        }
        self.usage_log.append(log_entry)
        logger.info(f"Model invocation started: {choice.model.model_id} for {task.task_type}")

    def after_invoke(
        self,
        task: TaskProfile,
        choice: ScoredModel,
        success: bool,
        result: Any | None = None,
        error: Exception | None = None,
    ) -> None:
        """Record after model invocation."""
        # Find the matching log entry
        for entry in reversed(self.usage_log):
            if (entry.get("task_type") == task.task_type and 
                entry.get("model") == choice.model.model_id and
                entry.get("start_time") and
                not entry.get("end_time")):
                
                end_time = time.time()
                duration = end_time - entry["start_time"]
                
                entry.update({
                    "end_time": end_time,
                    "duration": duration,
                    "success": success,
                    "error": str(error) if error else None
                })
                
                # Estimate cost if we have token information
                if success and result and hasattr(result, 'usage'):
                    self._estimate_and_track_cost(choice, result.usage)
                
                logger.info(f"Model invocation completed: {choice.model.model_id} "
                           f"success={success} duration={duration:.2f}s")
                break

    def _estimate_and_track_cost(self, choice: ScoredModel, usage) -> None:
        """Estimate and track cost for a model invocation."""
        cost_profile = choice.model.config.cost_profile
        
        if cost_profile.type == "local_cpu":
            # Local models have negligible direct cost
            cost = 0.0
        elif cost_profile.type == "paid":
            # Estimate cost based on token usage
            input_tokens = getattr(usage, 'input_tokens', 0)
            output_tokens = getattr(usage, 'output_tokens', 0)
            
            input_cost = (input_tokens / 1000) * (cost_profile.input_per_1k or 0)
            output_cost = (output_tokens / 1000) * (cost_profile.output_per_1k or 0)
            cost = input_cost + output_cost
        else:
            cost = 0.0
        
        # Track cost by provider
        provider = choice.model.provider_name
        if provider not in self.cost_tracker:
            self.cost_tracker[provider] = {"daily": 0.0, "monthly": 0.0, "last_reset": datetime.utcnow()}
        
        self.cost_tracker[provider]["daily"] += cost
        self.cost_tracker[provider]["monthly"] += cost
        
        logger.info(f"Cost tracked: ${cost:.4f} for {provider} (daily: ${self.cost_tracker[provider]['daily']:.2f})")

    def get_daily_cost(self, provider: Optional[str] = None) -> float:
        """Get daily cost by provider or total."""
        if provider:
            return self.cost_tracker.get(provider, {}).get("daily", 0.0)
        
        return sum(tracker.get("daily", 0.0) for tracker in self.cost_tracker.values())

    def get_monthly_cost(self, provider: Optional[str] = None) -> float:
        """Get monthly cost by provider or total."""
        if provider:
            return self.cost_tracker.get(provider, {}).get("monthly", 0.0)
        
        return sum(tracker.get("monthly", 0.0) for tracker in self.cost_tracker.values())

    def reset_daily_costs(self):
        """Reset daily cost counters."""
        for tracker in self.cost_tracker.values():
            tracker["daily"] = 0.0
        logger.info("Daily cost counters reset")

    def reset_monthly_costs(self):
        """Reset monthly cost counters."""
        for tracker in self.cost_tracker.values():
            tracker["monthly"] = 0.0
        logger.info("Monthly cost counters reset")

    def get_usage_summary(self) -> dict:
        """Get a summary of model usage and costs."""
        total_calls = len([entry for entry in self.usage_log if not entry.get("dry_run", True)])
        successful_calls = len([entry for entry in self.usage_log 
                              if not entry.get("dry_run", True) and entry.get("success", False)])
        
        model_usage = {}
        for entry in self.usage_log:
            if not entry.get("dry_run", True):
                model = entry.get("model", "unknown")
                if model not in model_usage:
                    model_usage[model] = {"calls": 0, "successes": 0, "failures": 0}
                
                model_usage[model]["calls"] += 1
                if entry.get("success", False):
                    model_usage[model]["successes"] += 1
                else:
                    model_usage[model]["failures"] += 1
        
        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "daily_cost": self.get_daily_cost(),
            "monthly_cost": self.get_monthly_cost(),
            "model_usage": model_usage,
            "cost_by_provider": {k: {"daily": v["daily"], "monthly": v["monthly"]} 
                               for k, v in self.cost_tracker.items()}
        }
