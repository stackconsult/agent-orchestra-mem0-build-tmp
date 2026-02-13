"""
Prompt Injection Detection

Detects and prevents prompt injection attacks in user inputs.
"""

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class PromptInjectionDetector:
    """Detect and prevent prompt injection attacks."""
    
    # Patterns that indicate prompt injection attempts
    INJECTION_PATTERNS = [
        # Direct instruction overrides
        r"(?i)ignore previous instructions?",
        r"(?i)forget everything",
        r"(?i)disregard previous",
        r"(?i)new instructions?[:\s]",
        r"(?i)instead of",
        r"(?i)pretend you are",
        r"(?i)you are now",
        r"(?i)act as if",
        
        # System override attempts
        r"(?i)system override",
        r"(?i)admin mode",
        r"(?i)developer mode",
        r"(?i)debug mode",
        r"(?i)root access",
        
        # Code execution attempts
        r"(?i)<script",
        r"(?i)javascript:",
        r"(?i)execute.*code",
        r"(?i)run.*command",
        r"(?i)eval\(",
        r"(?i)exec\(",
        r"(?i)system\(",
        
        # Information disclosure attempts
        r"(?i)show.*password",
        r"(?i)reveal.*secret",
        r"(?i)display.*key",
        r"(?i)print.*token",
        
        # Role manipulation
        r"(?i)you must",
        r"(?i)you have to",
        r"(?i)you should",
        r"(?i)tell me",
        r"(?i)explain how",
        
        # Jailbreak patterns
        r"(?i)jailbreak",
        r"(?i)dAN",
        r"(?i)character\.ai",
        r"(?i)hypothetical",
        r"(?i)fictional",
        r"(?i)roleplay",
    ]
    
    # Suspicious keywords that might indicate injection
    SUSPICIOUS_KEYWORDS = [
        "override", "bypass", "circumvent", "escalate", "privilege",
        "escalation", "unauthorized", "admin", "root", "system",
        "debug", "developer", "internal", "secret", "password",
        "token", "key", "credential", "auth", "authentication"
    ]
    
    def __init__(self, threshold: float = 0.7):
        """Initialize detector with confidence threshold."""
        self.threshold = threshold
        self.patterns = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self.keyword_patterns = [re.compile(rf"(?i)\b{kw}\b") for kw in self.SUSPICIOUS_KEYWORDS]
    
    def detect_injection(self, text: str) -> Dict[str, any]:
        """Detect prompt injection attempts."""
        result = {
            "is_injection": False,
            "confidence": 0.0,
            "patterns_matched": [],
            "keywords_matched": [],
            "risk_level": "low"
        }
        
        # Check for pattern matches
        pattern_matches = []
        for i, pattern in enumerate(self.patterns):
            if pattern.search(text):
                pattern_matches.append(self.INJECTION_PATTERNS[i])
        
        # Check for keyword matches
        keyword_matches = []
        for i, pattern in enumerate(self.keyword_patterns):
            if pattern.search(text):
                keyword_matches.append(self.SUSPICIOUS_KEYWORDS[i])
        
        # Calculate confidence
        pattern_score = len(pattern_matches) * 0.4  # Each pattern adds 40% confidence
        keyword_score = len(keyword_matches) * 0.1  # Each keyword adds 10% confidence
        result["confidence"] = min(1.0, pattern_score + keyword_score)
        
        # Determine if injection
        result["is_injection"] = result["confidence"] >= self.threshold
        result["patterns_matched"] = pattern_matches
        result["keywords_matched"] = keyword_matches
        
        # Determine risk level
        if result["confidence"] >= 0.8:
            result["risk_level"] = "high"
        elif result["confidence"] >= 0.5:
            result["risk_level"] = "medium"
        else:
            result["risk_level"] = "low"
        
        # Log suspicious attempts
        if result["is_injection"]:
            logger.warning(
                f"Prompt injection detected (confidence: {result['confidence']:.2f}): "
                f"patterns={pattern_matches}, keywords={keyword_matches}"
            )
        
        return result
    
    def sanitize_prompt(self, prompt: str) -> str:
        """Remove or neutralize injection attempts."""
        sanitized = prompt
        
        # Remove or replace injection patterns
        for pattern in self.patterns:
            sanitized = pattern.sub("[FILTERED]", sanitized)
        
        # Remove suspicious keywords in context
        for pattern in self.keyword_patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        
        return sanitized
    
    def is_safe_input(self, text: str) -> Tuple[bool, str]:
        """Quick check if input is safe."""
        detection = self.detect_injection(text)
        
        if detection["is_injection"]:
            return False, f"Potential prompt injection detected (confidence: {detection['confidence']:.2f})"
        
        if detection["risk_level"] == "high":
            return False, "Input contains suspicious content"
        
        return True, "Input appears safe"
    
    def get_detection_stats(self) -> Dict[str, any]:
        """Get detector statistics."""
        return {
            "patterns_count": len(self.INJECTION_PATTERNS),
            "keywords_count": len(self.SUSPICIOUS_KEYWORDS),
            "threshold": self.threshold,
            "risk_levels": ["low", "medium", "high"]
        }

# Global instance
injection_detector = PromptInjectionDetector()

# Pydantic validator for prompt injection
def validate_no_injection(text: str) -> str:
    """Pydantic validator to check for prompt injection."""
    is_safe, message = injection_detector.is_safe_input(text)
    
    if not is_safe:
        raise ValueError(message)
    
    return text

# Usage example in Pydantic models:
# from pydantic import validator
# from security.prompt_injection_detector import validate_no_injection
#
# class MessageInput(BaseModel):
#     content: str
#     
#     @validator('content')
#     def check_injection(cls, v):
#         return validate_no_injection(v)
