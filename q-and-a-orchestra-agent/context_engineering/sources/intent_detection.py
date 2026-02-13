"""
Intent Detection Context Source - Builds Intent Layer

StackConsulting Pattern: Detect what job the user is hiring the system to do
using message analysis, task_type hints, and session history.
"""

import re
from typing import Dict, Any, Optional, List, Tuple

from ..models import IntentContext

logger = __import__("logging").getLogger(__name__)

# Intent classification patterns
INTENT_PATTERNS = {
    "architecture_design": [
        r"architecture",
        r"design.*system",
        r"system.*design",
        r"technical.*design",
        r"scalability",
        r"microservices",
        r"monolith",
        r"component.*design",
    ],
    "repo_analysis": [
        r"analyze.*repo",
        r"codebase.*analysis",
        r"understand.*code",
        r"code.*review",
        r"technical.*debt",
        r"repository.*analysis",
    ],
    "implementation": [
        r"implement",
        r"build.*feature",
        r"code.*implementation",
        r"develop.*solution",
        r"write.*code",
        r"create.*component",
    ],
    "troubleshooting": [
        r"bug",
        r"error",
        r"issue",
        r"problem",
        r"not.*working",
        r"fix.*issue",
        r"debug",
        r"troubleshoot",
    ],
    "security_analysis": [
        r"security",
        r"vulnerability",
        r"threat.*model",
        r"security.*review",
        r"penetration.*test",
        r"security.*audit",
    ],
    "performance_optimization": [
        r"performance",
        r"optimize",
        r"slow",
        r"bottleneck",
        r"latency",
        r"throughput",
        r"scaling",
    ],
    "documentation": [
        r"document",
        r"readme",
        r"api.*doc",
        r"technical.*writing",
        r"knowledge.*base",
    ],
    "planning": [
        r"plan",
        r"roadmap",
        r"strategy",
        r"migrate",
        r"refactor.*plan",
        r"project.*plan",
    ],
}

# Success criteria templates
SUCCESS_CRITERIA_TEMPLATES = {
    "architecture_design": "Deliver a comprehensive architecture diagram with component relationships, technology choices, and scalability considerations.",
    "repo_analysis": "Provide actionable insights about codebase structure, technical debt, and specific recommendations for improvement.",
    "implementation": "Generate production-ready code with proper error handling, tests, and integration points clearly defined.",
    "troubleshooting": "Identify root cause, provide clear reproduction steps, and offer a tested solution with rollback plan.",
    "security_analysis": "Identify vulnerabilities, assess risk levels, and provide prioritized remediation steps.",
    "performance_optimization": "Pinpoint bottlenecks, quantify improvements, and provide implementation steps with metrics.",
    "documentation": "Create clear, comprehensive documentation that enables team autonomy and reduces onboarding time.",
    "planning": "Deliver a phased implementation plan with dependencies, risks, and success metrics clearly defined.",
}


def detect_intent(message: str, task_type: Optional[str] = None, session_id: Optional[str] = None) -> IntentContext:
    """
    Detect user intent from message and optional task_type.
    
    Args:
        message: User message text
        task_type: Optional explicit task type from request
        session_id: Optional session ID for context
    
    Returns:
        IntentContext with detected intent and metadata
    """
    # Normalize message for analysis
    message_lower = message.lower()
    
    # If task_type is explicitly provided, use it as primary hint
    if task_type:
        primary_intent = task_type.lower().replace(" ", "_")
        confidence_score = 0.9
    else:
        # Classify intent using pattern matching
        primary_intent, confidence_score = _classify_intent_from_message(message_lower)
    
    # Determine success criteria based on intent
    success_criteria = SUCCESS_CRITERIA_TEMPLATES.get(primary_intent, "Deliver a specific, actionable answer with clear next steps.")
    
    # Set constraints based on intent type
    constraints = _get_intent_constraints(primary_intent)
    
    # Determine escalation path for complex intents
    escalation_path = _get_escalation_path(primary_intent)
    
    return IntentContext(
        primary_intent=primary_intent,
        task_type=task_type,
        success_criteria=success_criteria,
        constraints=constraints,
        confidence_score=confidence_score,
        escalation_path=escalation_path,
    )


def _classify_intent_from_message(message: str) -> Tuple[str, float]:
    """
    Classify intent using pattern matching.
    
    Returns:
        Tuple of (intent_name, confidence_score)
    """
    intent_scores = {}
    
    # Score each intent based on pattern matches
    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        matches = 0
        
        for pattern in patterns:
            if re.search(pattern, message):
                matches += 1
                # Give more weight to more specific patterns
                if len(pattern.split()) > 2:
                    score += 1.5
                else:
                    score += 1
        
        if matches > 0:
            # Normalize score by number of patterns
            intent_scores[intent] = score / len(patterns)
    
    if not intent_scores:
        # Default to general assistance if no patterns match
        return "general_assistance", 0.5
    
    # Return intent with highest score
    best_intent = max(intent_scores.items(), key=lambda x: x[1])
    confidence = min(best_intent[1], 1.0)  # Cap at 1.0
    
    return best_intent[0], confidence


def _get_intent_constraints(intent: str) -> Dict[str, Any]:
    """
    Get constraints specific to the detected intent.
    """
    constraints = {"max_iterations": 3}
    
    if intent == "architecture_design":
        constraints.update({
            "require_diagrams": True,
            "consider_scalability": True,
            "include_technology_rationale": True,
        })
    elif intent == "security_analysis":
        constraints.update({
            "require_compliance_check": True,
            "minimum_vulnerability_severity": "medium",
            "include_mitigation_steps": True,
        })
    elif intent == "performance_optimization":
        constraints.update({
            "require_benchmarks": True,
            "include_before_after": True,
            "quantify_improvements": True,
        })
    elif intent == "implementation":
        constraints.update({
            "require_tests": True,
            "include_error_handling": True,
            "follow_style_guide": True,
        })
    
    return constraints


def _get_escalation_path(intent: str) -> Optional[str]:
    """
    Determine escalation path for complex intents.
    """
    escalation_map = {
        "security_analysis": "security_team",
        "architecture_design": "senior_architect",
        "performance_optimization": "performance_engineer",
        "troubleshooting": "senior_developer",
    }
    
    return escalation_map.get(intent)


def refine_intent_with_history(
    current_intent: IntentContext,
    session_history: List[Dict[str, Any]]
) -> IntentContext:
    """
    Refine intent based on session history.
    
    Args:
        current_intent: Initially detected intent
        session_history: Previous messages in the session
    
    Returns:
        Refined IntentContext
    """
    if not session_history:
        return current_intent
    
    # Check for intent shifts or clarifications
    recent_messages = session_history[-3:]  # Look at last 3 messages
    
    # If user is asking follow-up questions, maintain current intent
    follow_up_indicators = ["what about", "how do i", "can you explain", "tell me more"]
    for msg in recent_messages:
        msg_text = msg.get("message", "").lower()
        if any(indicator in msg_text for indicator in follow_up_indicators):
            current_intent.constraints["is_follow_up"] = True
            break
    
    # If user is asking for different type of help, detect shift
    shift_indicators = ["actually", "wait", "instead", "change of plans"]
    for msg in recent_messages:
        msg_text = msg.get("message", "").lower()
        if any(indicator in msg_text for indicator in shift_indicators):
            # Re-detect intent based on latest message
            new_intent = detect_intent(msg_text)
            current_intent.primary_intent = new_intent.primary_intent
            current_intent.success_criteria = new_intent.success_criteria
            current_intent.constraints.update(new_intent.constraints)
            break
    
    return current_intent
