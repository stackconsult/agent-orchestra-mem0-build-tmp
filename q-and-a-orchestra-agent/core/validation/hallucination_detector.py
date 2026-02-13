"""
Hallucination Detector

Detects factual inconsistencies and potential hallucinations
in model responses using NLI models and consistency checks.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class HallucinationResult:
    """Result of hallucination detection."""
    hallucination_probability: float  # 0-1
    inconsistent_statements: List[str]
    confidence_score: float
    analysis_details: Dict[str, Any]
    
    def has_hallucination(self, threshold: float = 0.3) -> bool:
        """Check if hallucination is detected above threshold."""
        return self.hallucination_probability >= threshold


class HallucinationDetector:
    """Detects hallucinations in model responses."""
    
    def __init__(self,
                 model_name: str = "facebook/bart-large-mnli",
                 confidence_threshold: float = 0.3):
        """Initialize hallucination detector."""
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.nli_pipeline = None
        self.initialized = False
        
        # Pattern-based detection rules
        self.factual_patterns = [
            r"\b\d{4}\b",  # Years
            r"\$\d+(?:,\d{3})*(?:\.\d{2})?",  # Money amounts
            r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percent|%)",  # Percentages
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\d{4}",  # Events with years
        ]
        
        # Uncertainty indicators
        self.uncertainty_indicators = [
            "might", "could", "perhaps", "possibly", "probably",
            "seems", "appears", "suggests", "indicates", "may"
        ]
        
        # Factual claim indicators
        self.factual_indicators = [
            "according to", "research shows", "studies indicate",
            "data suggests", "evidence shows", "it is known that"
        ]
    
    async def initialize(self):
        """Initialize the NLI model."""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, using pattern-based detection only")
            self.initialized = True
            return
        
        try:
            # Initialize NLI pipeline
            self.nli_pipeline = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1  # Use CPU
            )
            
            self.initialized = True
            logger.info(f"Hallucination detector initialized with model {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize NLI model: {e}")
            # Fall back to pattern-based detection
            self.initialized = True
    
    async def detect_hallucination(self,
                                 prompt: str,
                                 response: str,
                                 context: Optional[Dict[str, Any]] = None) -> HallucinationResult:
        """Detect hallucinations in response compared to prompt."""
        if not self.initialized:
            await self.initialize()
        
        # Extract statements from response
        statements = self._extract_statements(response)
        
        # Analyze each statement
        inconsistent_statements = []
        statement_scores = []
        
        for statement in statements:
            score = await self._analyze_statement_consistency(statement, prompt, context)
            statement_scores.append(score)
            
            if score < (1 - self.confidence_threshold):
                inconsistent_statements.append(statement)
        
        # Calculate overall hallucination probability
        if statement_scores:
            hallucination_probability = 1 - (sum(statement_scores) / len(statement_scores))
        else:
            hallucination_probability = 0.0
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(statement_scores)
        
        # Analysis details
        analysis_details = {
            "total_statements": len(statements),
            "inconsistent_count": len(inconsistent_statements),
            "statement_scores": statement_scores,
            "detection_method": "nli" if self.nli_pipeline else "pattern_based"
        }
        
        return HallucinationResult(
            hallucination_probability=hallucination_probability,
            inconsistent_statements=inconsistent_statements,
            confidence_score=confidence_score,
            analysis_details=analysis_details
        )
    
    def _extract_statements(self, text: str) -> List[str]:
        """Extract factual statements from text."""
        statements = []
        
        # Split by sentences
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains factual indicators
            has_factual_content = (
                any(pattern.search(sentence) for pattern in self.factual_patterns) or
                any(indicator in sentence.lower() for indicator in self.factual_indicators)
            )
            
            # Skip sentences with uncertainty indicators (less likely to be factual claims)
            has_uncertainty = any(indicator in sentence.lower() for indicator in self.uncertainty_indicators)
            
            if has_factual_content and not has_uncertainty:
                statements.append(sentence)
        
        return statements
    
    async def _analyze_statement_consistency(self,
                                          statement: str,
                                          prompt: str,
                                          context: Optional[Dict[str, Any]] = None) -> float:
        """Analyze consistency of a statement with prompt/context."""
        if self.nli_pipeline:
            return await self._nli_consistency_check(statement, prompt, context)
        else:
            return self._pattern_consistency_check(statement, prompt, context)
    
    async def _nli_consistency_check(self,
                                  statement: str,
                                  prompt: str,
                                  context: Optional[Dict[str, Any]] = None) -> float:
        """Use NLI model to check consistency."""
        try:
            # Prepare candidate labels
            candidate_labels = ["consistent", "contradictory", "neutral"]
            
            # Check statement against prompt
            result = self.nli_pipeline(
                statement,
                candidate_labels,
                hypothesis_template="This statement is {} with the prompt."
            )
            
            # Get consistency score
            labels = result["labels"]
            scores = result["scores"]
            
            consistency_score = 0.0
            for label, score in zip(labels, scores):
                if label == "consistent":
                    consistency_score = score
                elif label == "contradictory":
                    consistency_score = 1 - score
                # neutral doesn't affect score
            
            return consistency_score
            
        except Exception as e:
            logger.error(f"NLI consistency check failed: {e}")
            return self._pattern_consistency_check(statement, prompt, context)
    
    def _pattern_consistency_check(self,
                                 statement: str,
                                 prompt: str,
                                 context: Optional[Dict[str, Any]] = None) -> float:
        """Pattern-based consistency check."""
        # Extract key entities from both texts
        statement_entities = self._extract_entities(statement)
        prompt_entities = self._extract_entities(prompt)
        
        # Check for contradictions
        contradictions = self._detect_contradictions(statement, prompt)
        
        # Check for unsupported claims
        unsupported_claims = self._detect_unsupported_claims(statement, prompt)
        
        # Calculate consistency score
        entity_overlap = len(statement_entities & prompt_entities) / max(len(statement_entities), 1)
        
        # Penalize contradictions and unsupported claims
        contradiction_penalty = len(contradictions) * 0.3
        unsupported_penalty = len(unsupported_claims) * 0.2
        
        consistency_score = max(0, entity_overlap - contradiction_penalty - unsupported_penalty)
        
        return min(consistency_score, 1.0)
    
    def _extract_entities(self, text: str) -> set:
        """Extract entities from text using patterns."""
        entities = set()
        
        # Extract years
        years = re.findall(r"\b(19|20)\d{2}\b", text)
        entities.update(years)
        
        # Extract money amounts
        money = re.findall(r"\$\d+(?:,\d{3})*(?:\.\d{2})?", text)
        entities.update(money)
        
        # Extract percentages
        percentages = re.findall(r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:percent|%)", text)
        entities.update(percentages)
        
        # Extract proper nouns (simplified)
        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)
        entities.update(proper_nouns)
        
        return entities
    
    def _detect_contradictions(self, statement: str, prompt: str) -> List[str]:
        """Detect contradictions between statement and prompt."""
        contradictions = []
        
        # Simple contradiction patterns
        contradiction_patterns = [
            (r"\b(no|not|never)\s+(\w+)", r"\b\1\s+\2"),
            (r"\b(\w+)\s+(is|are)\s+not\b", r"\b\1\s+(is|are)\b"),
        ]
        
        for pattern, reverse_pattern in contradiction_patterns:
            statement_matches = re.findall(pattern, statement, re.IGNORECASE)
            for match in statement_matches:
                if isinstance(match, tuple):
                    match = " ".join(match)
                
                # Check if opposite exists in prompt
                if re.search(reverse_pattern.replace("\\1", match), prompt, re.IGNORECASE):
                    contradictions.append(match)
        
        return contradictions
    
    def _detect_unsupported_claims(self, statement: str, prompt: str) -> List[str]:
        """Detect claims in statement not supported by prompt."""
        unsupported = []
        
        # Extract factual claims from statement
        statement_facts = self._extract_factual_claims(statement)
        prompt_facts = self._extract_factual_claims(prompt)
        
        # Check if statement facts are supported by prompt
        for fact in statement_facts:
            is_supported = False
            
            for prompt_fact in prompt_facts:
                if self._facts_compatible(fact, prompt_fact):
                    is_supported = True
                    break
            
            if not is_supported:
                unsupported.append(fact)
        
        return unsupported
    
    def _extract_factual_claims(self, text: str) -> List[str]:
        """Extract factual claims from text."""
        claims = []
        
        # Look for sentences with factual indicators
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if any(indicator in sentence.lower() for indicator in self.factual_indicators):
                claims.append(sentence)
        
        return claims
    
    def _facts_compatible(self, fact1: str, fact2: str) -> bool:
        """Check if two facts are compatible."""
        # Simple compatibility check - in practice, this would be more sophisticated
        fact1_entities = self._extract_entities(fact1)
        fact2_entities = self._extract_entities(fact2)
        
        # If they share entities, they might be compatible
        entity_overlap = len(fact1_entities & fact2_entities) > 0
        
        return entity_overlap
    
    def _calculate_confidence_score(self, statement_scores: List[float]) -> float:
        """Calculate confidence in the hallucination detection."""
        if not statement_scores:
            return 0.0
        
        # Confidence based on consistency of scores
        avg_score = sum(statement_scores) / len(statement_scores)
        variance = sum((score - avg_score) ** 2 for score in statement_scores) / len(statement_scores)
        
        # Higher variance means lower confidence
        confidence = max(0, 1 - variance)
        
        return confidence
    
    async def batch_detect_hallucination(self,
                                      prompts_responses: List[Tuple[str, str]],
                                      context: Optional[Dict[str, Any]] = None) -> List[HallucinationResult]:
        """Detect hallucinations in batch."""
        detection_tasks = []
        
        for prompt, response in prompts_responses:
            task = self.detect_hallucination(prompt, response, context)
            detection_tasks.append(task)
        
        results = await asyncio.gather(*detection_tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch hallucination detection error: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_detector_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "model_name": self.model_name,
            "confidence_threshold": self.confidence_threshold,
            "initialized": self.initialized,
            "nli_available": self.nli_pipeline is not None,
            "factual_patterns_count": len(self.factual_patterns),
            "uncertainty_indicators_count": len(self.uncertainty_indicators)
        }
    
    def update_confidence_threshold(self, threshold: float):
        """Update confidence threshold."""
        self.confidence_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Hallucination confidence threshold updated to {self.confidence_threshold}")
