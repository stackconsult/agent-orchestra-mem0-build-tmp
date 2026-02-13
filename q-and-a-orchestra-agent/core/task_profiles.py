# core/task_profiles.py
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel


TaskType = Literal["qa", "planning", "routing", "coding", "summarization", "vision", "critic"]


class TaskProfile(BaseModel):
    task_type: TaskType
    criticality: Literal["low", "medium", "high"] = "medium"
    latency_sensitivity: Literal["low", "medium", "high"] = "medium"
    context_size: int = 0
    tool_use_required: bool = False
    budget_sensitivity: Literal["low", "medium", "high"] = "medium"
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
