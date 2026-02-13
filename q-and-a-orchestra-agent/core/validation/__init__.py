"""
Validation Module

Response validation system with hallucination detection,
quality assessment, and task-specific validation.

Components:
- ResponseValidator: Main validation orchestrator
- HallucinationDetector: Detects factual inconsistencies
- ToxicityChecker: Detects harmful content
- FactVerifier: Verifies claims against knowledge base
- TaskValidators: Task-specific validation logic
"""

from .response_validator import ResponseValidator, ValidationResult, ValidationIssue
from .hallucination_detector import HallucinationDetector, HallucinationResult
from .toxicity_checker import ToxicityChecker, ToxicityResult
from .fact_verifier import FactVerifier, FactCheckResult
from .task_validators import TaskValidatorRegistry, CodeValidator, MathValidator, SummaryValidator

__all__ = [
    "ResponseValidator",
    "ValidationResult",
    "ValidationIssue",
    "HallucinationDetector",
    "HallucinationResult",
    "ToxicityChecker", 
    "ToxicityResult",
    "FactVerifier",
    "FactCheckResult",
    "TaskValidatorRegistry",
    "CodeValidator",
    "MathValidator",
    "SummaryValidator"
]
