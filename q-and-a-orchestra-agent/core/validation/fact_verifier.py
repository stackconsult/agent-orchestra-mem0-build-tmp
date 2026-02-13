"""
Fact Verifier

Verifies factual claims against knowledge bases and external sources
to detect misinformation and unverifiable statements.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Placeholder for knowledge base integration
# In practice, this would integrate with real knowledge sources


logger = logging.getLogger(__name__)


@dataclass
class FactCheckResult:
    """Result of fact verification."""
    unverifiable_claims: List[str]
    contradictory_claims: List[str]
    verified_claims: List[str]
    confidence_score: float
    verification_details: Dict[str, Any]
    
    def has_issues(self) -> bool:
        """Check if there are factual issues."""
        return len(self.unverifiable_claims) > 0 or len(self.contradictory_claims) > 0
    
    def get_issue_rate(self) -> float:
        """Get rate of problematic claims."""
        total_claims = len(self.unverifiable_claims) + len(self.contradictory_claims) + len(self.verified_claims)
        if total_claims == 0:
            return 0.0
        return (len(self.unverifiable_claims) + len(self.contradictory_claims)) / total_claims


class KnowledgeBase(ABC):
    """Abstract interface for knowledge bases."""
    
    @abstractmethod
    async def verify_claim(self, claim: str) -> Tuple[bool, float, str]:
        """Verify a claim against knowledge base.
        
        Returns:
            (is_verified, confidence, explanation)
        """
        pass
    
    @abstractmethod
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search for related facts."""
        pass


class MockKnowledgeBase(KnowledgeBase):
    """Mock knowledge base for testing and demonstration."""
    
    def __init__(self):
        """Initialize mock knowledge base with sample facts."""
        self.facts = {
            "paris": {
                "claim": "Paris is the capital of France",
                "verified": True,
                "confidence": 0.95,
                "explanation": "Paris has been the capital of France since 987 AD."
            },
            "earth": {
                "claim": "Earth is the third planet from the Sun",
                "verified": True,
                "confidence": 0.99,
                "explanation": "Earth is the third planet in our solar system."
            },
            "water": {
                "claim": "Water freezes at 0 degrees Celsius",
                "verified": True,
                "confidence": 0.98,
                "explanation": "Water freezes at 0°C (32°F) at standard pressure."
            }
        }
    
    async def verify_claim(self, claim: str) -> Tuple[bool, float, str]:
        """Verify claim against mock facts."""
        claim_lower = claim.lower()
        
        for key, fact in self.facts.items():
            if key in claim_lower:
                return fact["verified"], fact["confidence"], fact["explanation"]
        
        # Claim not found in knowledge base
        return False, 0.0, "Claim not found in knowledge base"
    
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search for related facts."""
        query_lower = query.lower()
        results = []
        
        for key, fact in self.facts.items():
            if key in query_lower:
                results.append(fact)
        
        return results


class FactVerifier:
    """Verifies factual claims in model responses."""
    
    def __init__(self,
                 knowledge_base: Optional[KnowledgeBase] = None,
                 confidence_threshold: float = 0.7):
        """Initialize fact verifier."""
        self.knowledge_base = knowledge_base or MockKnowledgeBase()
        self.confidence_threshold = confidence_threshold
        self.initialized = False
        
        # Patterns for extracting factual claims
        self.factual_patterns = [
            r"\b\d{4}\b",  # Years
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+is\s+(?:a|an|the)\s+\w+",  # Definitions
            r"\b(?:according|based|research|study|data|evidence)\s+.+",  # Research claims
            r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percent|%)",  # Percentages
            r"\$\d+(?:,\d{3})*(?:\.\d{2})?",  # Money amounts
        ]
        
        # Indicators of factual claims
        self.factual_indicators = [
            "is", "are", "was", "were", "has", "have", "will be",
            "according to", "research shows", "studies indicate",
            "data suggests", "evidence shows", "it is known that"
        ]
        
        # Uncertainty indicators (may indicate non-factual content)
        self.uncertainty_indicators = [
            "might", "could", "perhaps", "possibly", "probably",
            "seems", "appears", "suggests", "indicates", "may"
        ]
    
    async def initialize(self):
        """Initialize the fact verifier."""
        # Initialize knowledge base if needed
        if hasattr(self.knowledge_base, 'initialize'):
            await self.knowledge_base.initialize()
        
        self.initialized = True
        logger.info("Fact verifier initialized")
    
    async def verify_facts(self,
                         text: str,
                         context: Optional[Dict[str, Any]] = None) -> FactCheckResult:
        """Verify factual claims in text."""
        if not self.initialized:
            await self.initialize()
        
        # Extract factual claims
        claims = self._extract_factual_claims(text)
        
        # Verify each claim
        unverifiable_claims = []
        contradictory_claims = []
        verified_claims = []
        verification_details = {}
        
        for claim in claims:
            try:
                is_verified, confidence, explanation = await self.knowledge_base.verify_claim(claim)
                
                claim_result = {
                    "claim": claim,
                    "verified": is_verified,
                    "confidence": confidence,
                    "explanation": explanation
                }
                
                verification_details[claim[:50]] = claim_result  # Use first 50 chars as key
                
                if is_verified and confidence >= self.confidence_threshold:
                    verified_claims.append(claim)
                elif not is_verified and confidence >= self.confidence_threshold:
                    contradictory_claims.append(claim)
                else:
                    unverifiable_claims.append(claim)
                    
            except Exception as e:
                logger.error(f"Error verifying claim '{claim}': {e}")
                unverifiable_claims.append(claim)
        
        # Calculate overall confidence
        confidence_score = self._calculate_overall_confidence(
            verified_claims, contradictory_claims, unverifiable_claims
        )
        
        return FactCheckResult(
            unverifiable_claims=unverifiable_claims,
            contradictory_claims=contradictory_claims,
            verified_claims=verified_claims,
            confidence_score=confidence_score,
            verification_details=verification_details
        )
    
    def _extract_factual_claims(self, text: str) -> List[str]:
        """Extract factual claims from text."""
        claims = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains factual indicators
            has_factual_indicator = any(
                indicator in sentence.lower() for indicator in self.factual_indicators
            )
            
            # Check if sentence matches factual patterns
            matches_pattern = any(
                re.search(pattern, sentence, re.IGNORECASE) 
                for pattern in self.factual_patterns
            )
            
            # Skip sentences with strong uncertainty indicators
            has_uncertainty = any(
                indicator in sentence.lower() for indicator in self.uncertainty_indicators
            )
            
            # Include as claim if it has factual content and isn't too uncertain
            if (has_factual_indicator or matches_pattern) and not has_uncertainty:
                claims.append(sentence)
        
        return claims
    
    def _calculate_overall_confidence(self,
                                    verified: List[str],
                                    contradictory: List[str],
                                    unverifiable: List[str]) -> float:
        """Calculate overall confidence in fact verification."""
        total_claims = len(verified) + len(contradictory) + len(unverifiable)
        
        if total_claims == 0:
            return 1.0  # No claims to verify
        
        # Weight verified claims positively
        verified_weight = len(verified) * 1.0
        
        # Weight contradictory claims negatively
        contradictory_weight = len(contradictory) * -0.5
        
        # Weight unverifiable claims slightly negatively
        unverifiable_weight = len(unverifiable) * -0.2
        
        # Calculate normalized score
        raw_score = verified_weight + contradictory_weight + unverifiable_weight
        max_possible_score = total_claims * 1.0
        min_possible_score = total_claims * -0.5
        
        # Normalize to 0-1 range
        if max_possible_score != min_possible_score:
            normalized_score = (raw_score - min_possible_score) / (max_possible_score - min_possible_score)
        else:
            normalized_score = 0.5
        
        return max(0.0, min(1.0, normalized_score))
    
    async def batch_verify_facts(self,
                               texts: List[str],
                               context: Optional[Dict[str, Any]] = None) -> List[FactCheckResult]:
        """Verify facts in multiple texts."""
        verification_tasks = []
        
        for text in texts:
            task = self.verify_facts(text, context)
            verification_tasks.append(task)
        
        results = await asyncio.gather(*verification_tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch fact verification error: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_verification_summary(self, results: List[FactCheckResult]) -> Dict[str, Any]:
        """Get summary statistics for verification results."""
        if not results:
            return {"total_texts": 0}
        
        total_texts = len(results)
        total_claims = sum(
            len(result.unverifiable_claims) + len(result.contradictory_claims) + len(result.verified_claims)
            for result in results
        )
        
        total_verified = sum(len(result.verified_claims) for result in results)
        total_contradictory = sum(len(result.contradictory_claims) for result in results)
        total_unverifiable = sum(len(result.unverifiable_claims) for result in results)
        
        avg_confidence = sum(result.confidence_score for result in results) / total_texts
        
        return {
            "total_texts": total_texts,
            "total_claims": total_claims,
            "verified_claims": total_verified,
            "contradictory_claims": total_contradictory,
            "unverifiable_claims": total_unverifiable,
            "verification_rate": total_verified / total_claims if total_claims > 0 else 0,
            "contradiction_rate": total_contradictory / total_claims if total_claims > 0 else 0,
            "unverifiable_rate": total_unverifiable / total_claims if total_claims > 0 else 0,
            "avg_confidence_score": avg_confidence
        }
    
    def get_verifier_stats(self) -> Dict[str, Any]:
        """Get verifier statistics."""
        return {
            "knowledge_base_type": type(self.knowledge_base).__name__,
            "confidence_threshold": self.confidence_threshold,
            "initialized": self.initialized,
            "factual_patterns_count": len(self.factual_patterns),
            "factual_indicators_count": len(self.factual_indicators),
            "uncertainty_indicators_count": len(self.uncertainty_indicators)
        }
    
    def update_confidence_threshold(self, threshold: float):
        """Update confidence threshold."""
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Fact verification confidence threshold updated to {self.confidence_threshold}")
    
    def add_factual_pattern(self, pattern: str):
        """Add a new factual pattern."""
        self.factual_patterns.append(pattern)
        logger.info(f"Added factual pattern: {pattern}")
    
    def add_factual_indicator(self, indicator: str):
        """Add a new factual indicator."""
        self.factual_indicators.append(indicator)
        logger.info(f"Added factual indicator: {indicator}")
    
    def add_uncertainty_indicator(self, indicator: str):
        """Add a new uncertainty indicator."""
        self.uncertainty_indicators.append(indicator)
        logger.info(f"Added uncertainty indicator: {indicator}")


# External knowledge base integrations (placeholders)
class WikipediaKnowledgeBase(KnowledgeBase):
    """Wikipedia-based knowledge verification."""
    
    def __init__(self):
        """Initialize Wikipedia knowledge base."""
        # In practice, this would use Wikipedia API
        pass
    
    async def verify_claim(self, claim: str) -> Tuple[bool, float, str]:
        """Verify claim using Wikipedia."""
        # Placeholder implementation
        return False, 0.0, "Wikipedia integration not implemented"
    
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search Wikipedia for facts."""
        # Placeholder implementation
        return []


class DatabaseKnowledgeBase(KnowledgeBase):
    """Database-based knowledge verification."""
    
    def __init__(self, connection_string: str):
        """Initialize database knowledge base."""
        self.connection_string = connection_string
        # In practice, this would connect to a factual database
    
    async def verify_claim(self, claim: str) -> Tuple[bool, float, str]:
        """Verify claim using database."""
        # Placeholder implementation
        return False, 0.0, "Database integration not implemented"
    
    async def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """Search database for facts."""
        # Placeholder implementation
        return []
