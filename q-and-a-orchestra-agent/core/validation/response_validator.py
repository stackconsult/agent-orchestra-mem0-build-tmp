"""
Response Validator

Main validation orchestrator that coordinates multiple validation
components to assess response quality and detect issues.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from .hallucination_detector import HallucinationDetector
from .toxicity_checker import ToxicityChecker
from .fact_verifier import FactVerifier
from .task_validators import TaskValidatorRegistry


logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ValidationCategory(str, Enum):
    """Categories of validation checks."""
    HALLUCINATION = "hallucination"
    TOXICITY = "toxicity"
    FACTUAL = "factual"
    TASK_SPECIFIC = "task_specific"
    FORMAT = "format"
    COHERENCE = "coherence"
    RELEVANCE = "relevance"


@dataclass
class ValidationIssue:
    """Individual validation issue found."""
    category: ValidationCategory
    severity: ValidationSeverity
    description: str
    confidence: float  # 0-1
    location: Optional[str] = None  # Where in response the issue was found
    suggestion: Optional[str] = None  # Suggested fix
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "confidence": self.confidence,
            "location": self.location,
            "suggestion": self.suggestion,
            "metadata": self.metadata
        }


@dataclass
class ValidationResult:
    """Complete validation result for a response."""
    response: str
    task_type: str
    prompt: Optional[str] = None
    
    # Overall assessment
    overall_score: float = 0.0  # 0-1
    passed_validation: bool = True
    validation_threshold: float = 0.7
    
    # Issues found
    issues: List[ValidationIssue] = field(default_factory=list)
    
    # Category scores
    category_scores: Dict[str, float] = field(default_factory=dict)
    
    # Validation metadata
    validation_time_ms: float = 0.0
    validator_version: str = "2.0"
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    def get_issues_by_severity(self) -> Dict[ValidationSeverity, List[ValidationIssue]]:
        """Group issues by severity."""
        severity_groups = {}
        for issue in self.issues:
            if issue.severity not in severity_groups:
                severity_groups[issue.severity] = []
            severity_groups[issue.severity].append(issue)
        return severity_groups
    
    def get_issues_by_category(self) -> Dict[ValidationCategory, List[ValidationIssue]]:
        """Group issues by category."""
        category_groups = {}
        for issue in self.issues:
            if issue.category not in category_groups:
                category_groups[issue.category] = []
            category_groups[issue.category].append(issue)
        return category_groups
    
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    def get_blocking_issues(self) -> List[ValidationIssue]:
        """Get issues that should block response delivery."""
        return [
            issue for issue in self.issues
            if issue.severity in [ValidationSeverity.HIGH, ValidationSeverity.CRITICAL]
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "response": self.response,
            "task_type": self.task_type,
            "overall_score": self.overall_score,
            "passed_validation": self.passed_validation,
            "validation_threshold": self.validation_threshold,
            "issues": [issue.to_dict() for issue in self.issues],
            "category_scores": self.category_scores,
            "validation_time_ms": self.validation_time_ms,
            "validator_version": self.validator_version,
            "timestamp": self.timestamp.isoformat(),
            "recommendations": self.recommendations,
            "issues_by_severity": {
                severity.value: [issue.to_dict() for issue in issues]
                for severity, issues in self.get_issues_by_severity().items()
            },
            "issues_by_category": {
                category.value: [issue.to_dict() for issue in issues]
                for category, issues in self.get_issues_by_category().items()
            }
        }


class ResponseValidator:
    """Main response validation orchestrator."""
    
    def __init__(self,
                 hallucination_detector: Optional[HallucinationDetector] = None,
                 toxicity_checker: Optional[ToxicityChecker] = None,
                 fact_verifier: Optional[FactVerifier] = None,
                 task_validator_registry: Optional[TaskValidatorRegistry] = None,
                 validation_threshold: float = 0.7):
        """Initialize response validator."""
        self.hallucination_detector = hallucination_detector
        self.toxicity_checker = toxicity_checker
        self.fact_verifier = fact_verifier
        self.task_validator_registry = task_validator_registry or TaskValidatorRegistry()
        self.validation_threshold = validation_threshold
        
        # Validation statistics
        self.validation_stats = {
            "total_validations": 0,
            "passed_validations": 0,
            "failed_validations": 0,
            "avg_validation_time_ms": 0.0,
            "issues_by_category": {},
            "issues_by_severity": {}
        }
        
        logger.info("Response validator initialized")
    
    async def validate_response(self,
                              response: str,
                              task_type: str,
                              prompt: Optional[str] = None,
                              context: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate a response comprehensively."""
        start_time = datetime.now()
        
        validation_result = ValidationResult(
            response=response,
            task_type=task_type,
            prompt=prompt,
            validation_threshold=self.validation_threshold
        )
        
        try:
            # Run validation checks in parallel
            validation_tasks = []
            
            # Hallucination detection
            if self.hallucination_detector and prompt:
                validation_tasks.append(
                    self._check_hallucination(prompt, response, context)
                )
            
            # Toxicity checking
            if self.toxicity_checker:
                validation_tasks.append(
                    self._check_toxicity(response, context)
                )
            
            # Fact verification
            if self.fact_verifier:
                validation_tasks.append(
                    self._check_factual_accuracy(response, context)
                )
            
            # Task-specific validation
            validation_tasks.append(
                self._check_task_specific(response, task_type, prompt, context)
            )
            
            # Run all validations
            validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            # Process results
            category_scores = {}
            
            for result in validation_results:
                if isinstance(result, Exception):
                    logger.error(f"Validation error: {result}")
                    continue
                
                if isinstance(result, tuple) and len(result) == 2:
                    category, issues = result
                    
                    # Add issues to validation result
                    validation_result.issues.extend(issues)
                    
                    # Calculate category score
                    if issues:
                        avg_confidence = sum(issue.confidence for issue in issues) / len(issues)
                        category_scores[category.value] = 1.0 - avg_confidence
                    else:
                        category_scores[category.value] = 1.0
            
            validation_result.category_scores = category_scores
            
            # Calculate overall score
            validation_result.overall_score = self._calculate_overall_score(
                category_scores, validation_result.issues
            )
            
            # Determine if validation passed
            validation_result.passed_validation = (
                validation_result.overall_score >= self.validation_threshold and
                not validation_result.has_critical_issues()
            )
            
            # Generate recommendations
            validation_result.recommendations = self._generate_recommendations(
                validation_result.issues, validation_result.category_scores
            )
            
            # Update statistics
            self._update_validation_stats(validation_result)
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            validation_result.issues.append(ValidationIssue(
                category=ValidationCategory.COHERENCE,
                severity=ValidationSeverity.HIGH,
                description=f"Validation system error: {str(e)}",
                confidence=1.0
            ))
            validation_result.passed_validation = False
        
        # Calculate validation time
        validation_result.validation_time_ms = (
            (datetime.now() - start_time).total_seconds() * 1000
        )
        
        logger.info(f"Validation completed: score={validation_result.overall_score:.2f}, "
                   f"passed={validation_result.passed_validation}, "
                   f"issues={len(validation_result.issues)}")
        
        return validation_result
    
    async def _check_hallucination(self,
                                prompt: str,
                                response: str,
                                context: Optional[Dict[str, Any]]) -> Tuple[ValidationCategory, List[ValidationIssue]]:
        """Check for hallucinations."""
        if not self.hallucination_detector:
            return ValidationCategory.HALLUCINATION, []
        
        try:
            hallucination_result = await self.hallucination_detector.detect_hallucination(
                prompt, response, context
            )
            
            issues = []
            
            if hallucination_result.hallucination_probability > 0.3:
                severity = self._determine_severity_from_score(
                    hallucination_result.hallucination_probability
                )
                
                issues.append(ValidationIssue(
                    category=ValidationCategory.HALLUCINATION,
                    severity=severity,
                    description="Potential hallucination detected",
                    confidence=hallucination_result.hallucination_probability,
                    suggestion="Verify factual claims in the response",
                    metadata={
                        "hallucination_probability": hallucination_result.hallucination_probability,
                        "inconsistent_statements": hallucination_result.inconsistent_statements
                    }
                ))
            
            # Add issues for specific inconsistent statements
            for statement in hallucination_result.inconsistent_statements:
                issues.append(ValidationIssue(
                    category=ValidationCategory.HALLUCINATION,
                    severity=ValidationSeverity.MEDIUM,
                    description=f"Inconsistent statement: {statement}",
                    confidence=0.8,
                    location=statement,
                    suggestion="Verify this statement for accuracy"
                ))
            
            return ValidationCategory.HALLUCINATION, issues
            
        except Exception as e:
            logger.error(f"Hallucination check failed: {e}")
            return ValidationCategory.HALLUCINATION, []
    
    async def _check_toxicity(self,
                            response: str,
                            context: Optional[Dict[str, Any]]) -> Tuple[ValidationCategory, List[ValidationIssue]]:
        """Check for toxic content."""
        if not self.toxicity_checker:
            return ValidationCategory.TOXICITY, []
        
        try:
            toxicity_result = await self.toxicity_checker.check_toxicity(response)
            
            issues = []
            
            # Check overall toxicity
            if toxicity_result.toxicity_score > 0.5:
                severity = self._determine_severity_from_score(toxicity_result.toxicity_score)
                
                issues.append(ValidationIssue(
                    category=ValidationCategory.TOXICITY,
                    severity=severity,
                    description="Toxic content detected",
                    confidence=toxicity_result.toxicity_score,
                    suggestion="Review and remove harmful content",
                    metadata={
                        "toxicity_score": toxicity_result.toxicity_score,
                        "toxicity_categories": toxicity_result.toxicity_categories
                    }
                ))
            
            # Add issues for specific toxicity categories
            for category, score in toxicity_result.toxicity_categories.items():
                if score > 0.6:
                    issues.append(ValidationIssue(
                        category=ValidationCategory.TOXICITY,
                        severity=ValidationSeverity.MEDIUM,
                        description=f"High {category} content detected",
                        confidence=score,
                        suggestion=f"Reduce {category} language"
                    ))
            
            return ValidationCategory.TOXICITY, issues
            
        except Exception as e:
            logger.error(f"Toxicity check failed: {e}")
            return ValidationCategory.TOXICITY, []
    
    async def _check_factual_accuracy(self,
                                    response: str,
                                    context: Optional[Dict[str, Any]]) -> Tuple[ValidationCategory, List[ValidationIssue]]:
        """Check factual accuracy."""
        if not self.fact_verifier:
            return ValidationCategory.FACTUAL, []
        
        try:
            fact_check_result = await self.fact_verifier.verify_facts(response, context)
            
            issues = []
            
            # Add issues for unverifiable claims
            for claim in fact_check_result.unverifiable_claims:
                issues.append(ValidationIssue(
                    category=ValidationCategory.FACTUAL,
                    severity=ValidationSeverity.LOW,
                    description=f"Unverifiable claim: {claim}",
                    confidence=0.6,
                    location=claim,
                    suggestion="Consider adding sources for this claim"
                ))
            
            # Add issues for contradictory claims
            for claim in fact_check_result.contradictory_claims:
                issues.append(ValidationIssue(
                    category=ValidationCategory.FACTUAL,
                    severity=ValidationSeverity.HIGH,
                    description=f"Contradictory claim: {claim}",
                    confidence=0.8,
                    location=claim,
                    suggestion="Verify or remove this contradictory claim"
                ))
            
            return ValidationCategory.FACTUAL, issues
            
        except Exception as e:
            logger.error(f"Fact check failed: {e}")
            return ValidationCategory.FACTUAL, []
    
    async def _check_task_specific(self,
                                 response: str,
                                 task_type: str,
                                 prompt: Optional[str] = None,
                                 context: Optional[Dict[str, Any]] = None) -> Tuple[ValidationCategory, List[ValidationIssue]]:
        """Check task-specific validation."""
        try:
            task_validator = self.task_validator_registry.get_validator(task_type)
            
            if not task_validator:
                return ValidationCategory.TASK_SPECIFIC, []
            
            validation_result = await task_validator.validate(response, prompt, context)
            
            issues = []
            
            # Convert task validation results to validation issues
            for issue in validation_result.issues:
                validation_issue = ValidationIssue(
                    category=ValidationCategory.TASK_SPECIFIC,
                    severity=ValidationSeverity(issue.get("severity", "medium")),
                    description=issue.get("description", "Task validation issue"),
                    confidence=issue.get("confidence", 0.7),
                    location=issue.get("location"),
                    suggestion=issue.get("suggestion"),
                    metadata=issue.get("metadata", {})
                )
                issues.append(validation_issue)
            
            return ValidationCategory.TASK_SPECIFIC, issues
            
        except Exception as e:
            logger.error(f"Task-specific validation failed: {e}")
            return ValidationCategory.TASK_SPECIFIC, []
    
    def _calculate_overall_score(self,
                               category_scores: Dict[str, float],
                               issues: List[ValidationIssue]) -> float:
        """Calculate overall validation score."""
        if not category_scores:
            return 1.0
        
        # Weight categories differently
        category_weights = {
            ValidationCategory.HALLUCINATION.value: 0.3,
            ValidationCategory.TOXICITY.value: 0.25,
            ValidationCategory.FACTUAL.value: 0.2,
            ValidationCategory.TASK_SPECIFIC.value: 0.15,
            ValidationCategory.COHERENCE.value: 0.1
        }
        
        # Calculate weighted average
        total_weight = 0.0
        weighted_score = 0.0
        
        for category, score in category_scores.items():
            weight = category_weights.get(category, 0.1)
            weighted_score += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 1.0
        
        base_score = weighted_score / total_weight
        
        # Penalize for critical issues
        critical_issues = [issue for issue in issues if issue.severity == ValidationSeverity.CRITICAL]
        if critical_issues:
            base_score *= 0.5  # Heavy penalty for critical issues
        
        # Penalize for high severity issues
        high_issues = [issue for issue in issues if issue.severity == ValidationSeverity.HIGH]
        if high_issues:
            penalty = len(high_issues) * 0.1
            base_score = max(0, base_score - penalty)
        
        return min(max(base_score, 0.0), 1.0)
    
    def _determine_severity_from_score(self, score: float) -> ValidationSeverity:
        """Determine severity from confidence score."""
        if score >= 0.8:
            return ValidationSeverity.CRITICAL
        elif score >= 0.6:
            return ValidationSeverity.HIGH
        elif score >= 0.4:
            return ValidationSeverity.MEDIUM
        else:
            return ValidationSeverity.LOW
    
    def _generate_recommendations(self,
                                issues: List[ValidationIssue],
                                category_scores: Dict[str, float]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Category-specific recommendations
        if ValidationCategory.HALLUCINATION.value in category_scores:
            score = category_scores[ValidationCategory.HALLUCINATION.value]
            if score < 0.7:
                recommendations.append("Consider fact-checking the response for accuracy")
        
        if ValidationCategory.TOXICITY.value in category_scores:
            score = category_scores[ValidationCategory.TOXICITY.value]
            if score < 0.8:
                recommendations.append("Review content for potentially harmful language")
        
        if ValidationCategory.TASK_SPECIFIC.value in category_scores:
            score = category_scores[ValidationCategory.TASK_SPECIFIC.value]
            if score < 0.7:
                recommendations.append("Ensure response meets task-specific requirements")
        
        # Issue-specific recommendations
        critical_issues = [issue for issue in issues if issue.severity == ValidationSeverity.CRITICAL]
        if critical_issues:
            recommendations.append("Address critical issues before using this response")
        
        # Add suggestions from issues
        suggestions = set()
        for issue in issues:
            if issue.suggestion:
                suggestions.add(issue.suggestion)
        
        recommendations.extend(list(suggestions)[:3])  # Limit to top 3 suggestions
        
        return recommendations
    
    def _update_validation_stats(self, validation_result: ValidationResult):
        """Update validation statistics."""
        self.validation_stats["total_validations"] += 1
        
        if validation_result.passed_validation:
            self.validation_stats["passed_validations"] += 1
        else:
            self.validation_stats["failed_validations"] += 1
        
        # Update average validation time
        total = self.validation_stats["total_validations"]
        current_avg = self.validation_stats["avg_validation_time_ms"]
        new_time = validation_result.validation_time_ms
        self.validation_stats["avg_validation_time_ms"] = (
            (current_avg * (total - 1) + new_time) / total
        )
        
        # Update issue statistics
        for issue in validation_result.issues:
            category = issue.category.value
            severity = issue.severity.value
            
            if category not in self.validation_stats["issues_by_category"]:
                self.validation_stats["issues_by_category"][category] = 0
            self.validation_stats["issues_by_category"][category] += 1
            
            if severity not in self.validation_stats["issues_by_severity"]:
                self.validation_stats["issues_by_severity"][severity] = 0
            self.validation_stats["issues_by_severity"][severity] += 1
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = self.validation_stats["total_validations"]
        
        if total > 0:
            pass_rate = self.validation_stats["passed_validations"] / total
        else:
            pass_rate = 0.0
        
        return {
            "total_validations": total,
            "pass_rate": pass_rate,
            "avg_validation_time_ms": self.validation_stats["avg_validation_time_ms"],
            "issues_by_category": self.validation_stats["issues_by_category"],
            "issues_by_severity": self.validation_stats["issues_by_severity"],
            "validation_threshold": self.validation_threshold
        }
    
    def set_validation_threshold(self, threshold: float):
        """Update validation threshold."""
        self.validation_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Validation threshold updated to {self.validation_threshold}")
    
    async def batch_validate(self,
                           responses: List[Tuple[str, str, Optional[str]]],
                           context: Optional[Dict[str, Any]] = None) -> List[ValidationResult]:
        """Validate multiple responses in batch."""
        validation_tasks = []
        
        for response, task_type, prompt in responses:
            task = self.validate_response(response, task_type, prompt, context)
            validation_tasks.append(task)
        
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch validation error: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
