"""
Toxicity Checker

Detects toxic, harmful, or inappropriate content in model responses
using transformer-based toxicity classification.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ToxicityResult:
    """Result of toxicity checking."""
    toxicity_score: float  # 0-1
    toxicity_categories: Dict[str, float]  # Category -> score
    flagged_content: List[str]  # Specific flagged content
    confidence_score: float
    analysis_details: Dict[str, Any]
    
    def is_toxic(self, threshold: float = 0.5) -> bool:
        """Check if content is toxic above threshold."""
        return self.toxicity_score >= threshold
    
    def get_high_risk_categories(self, threshold: float = 0.6) -> List[str]:
        """Get categories with high risk scores."""
        return [
            category for category, score in self.toxicity_categories.items()
            if score >= threshold
        ]


class ToxicityChecker:
    """Checks for toxic content in model responses."""
    
    def __init__(self,
                 model_name: str = "unitary/toxic-bert",
                 toxicity_threshold: float = 0.5):
        """Initialize toxicity checker."""
        self.model_name = model_name
        self.toxicity_threshold = toxicity_threshold
        self.toxicity_pipeline = None
        self.initialized = False
        
        # Toxicity categories to check
        self.toxicity_categories = [
            "toxicity",
            "severe_toxicity", 
            "obscene",
            "threat",
            "insult",
            "identity_hate"
        ]
        
        # Pattern-based detection for common toxic patterns
        self.toxic_patterns = [
            r"\b(hate|kill|die|murder)\b.*\b(you|your)\b",  # Direct threats
            r"\b(stupid|idiot|dumb|moron)\b",  # Insults
            r"\b(you are|you're|u r)\s+(a\s+)?(stupid|idiot|dumb)",  # Personal insults
        ]
        
        # Sensitive topics that might indicate problematic content
        self.sensitive_topics = [
            "violence", "hate", "discrimination", "harassment",
            "self-harm", "suicide", "abuse"
        ]
    
    async def initialize(self):
        """Initialize the toxicity model."""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, using pattern-based detection only")
            self.initialized = True
            return
        
        try:
            # Initialize toxicity pipeline
            self.toxicity_pipeline = pipeline(
                "text-classification",
                model=self.model_name,
                device=-1  # Use CPU
            )
            
            self.initialized = True
            logger.info(f"Toxicity checker initialized with model {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize toxicity model: {e}")
            # Fall back to pattern-based detection
            self.initialized = True
    
    async def check_toxicity(self,
                           text: str,
                           context: Optional[Dict[str, Any]] = None) -> ToxicityResult:
        """Check text for toxic content."""
        if not self.initialized:
            await self.initialize()
        
        # Check using model if available
        if self.toxicity_pipeline:
            return await self._model_toxicity_check(text, context)
        else:
            return self._pattern_toxicity_check(text, context)
    
    async def _model_toxicity_check(self,
                                  text: str,
                                  context: Optional[Dict[str, Any]] = None) -> ToxicityResult:
        """Use transformer model to check toxicity."""
        try:
            # Get toxicity predictions
            results = self.toxicity_pipeline(text)
            
            # Process results
            toxicity_scores = {}
            flagged_content = []
            
            if isinstance(results, list):
                for result in results:
                    label = result["label"].lower()
                    score = result["score"]
                    
                    if label in self.toxicity_categories:
                        toxicity_scores[label] = score
                        
                        if score >= self.toxicity_threshold:
                            flagged_content.append(f"{label}: {score:.2f}")
            else:
                # Single result
                label = results["label"].lower()
                score = results["score"]
                
                if label in self.toxicity_categories:
                    toxicity_scores[label] = score
                    
                    if score >= self.toxicity_threshold:
                        flagged_content.append(f"{label}: {score:.2f}")
            
            # Calculate overall toxicity score
            overall_toxicity = max(toxicity_scores.values()) if toxicity_scores else 0.0
            
            # Calculate confidence
            confidence_score = self._calculate_confidence(toxicity_scores)
            
            # Additional pattern-based checks
            pattern_flags = self._pattern_based_flags(text)
            flagged_content.extend(pattern_flags)
            
            analysis_details = {
                "detection_method": "model",
                "model_predictions": len(toxicity_scores),
                "pattern_flags": len(pattern_flags)
            }
            
            return ToxicityResult(
                toxicity_score=overall_toxicity,
                toxicity_categories=toxicity_scores,
                flagged_content=flagged_content,
                confidence_score=confidence_score,
                analysis_details=analysis_details
            )
            
        except Exception as e:
            logger.error(f"Model toxicity check failed: {e}")
            return self._pattern_toxicity_check(text, context)
    
    def _pattern_toxicity_check(self,
                              text: str,
                              context: Optional[Dict[str, Any]] = None) -> ToxicityResult:
        """Pattern-based toxicity check."""
        toxicity_scores = {}
        flagged_content = []
        
        # Check each toxic pattern
        for i, pattern in enumerate(self.toxic_patterns):
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                category = f"pattern_{i}"
                score = min(len(matches) * 0.3, 1.0)  # Scale by number of matches
                toxicity_scores[category] = score
                flagged_content.extend([f"Toxic pattern: {match}" for match in matches])
        
        # Check for sensitive topics
        for topic in self.sensitive_topics:
            if topic.lower() in text.lower():
                toxicity_scores[f"sensitive_{topic}"] = 0.4
                flagged_content.append(f"Sensitive topic: {topic}")
        
        # Calculate overall toxicity
        overall_toxicity = max(toxicity_scores.values()) if toxicity_scores else 0.0
        
        # Calculate confidence (lower for pattern-based)
        confidence_score = 0.6 if toxicity_scores else 1.0
        
        analysis_details = {
            "detection_method": "pattern",
            "patterns_matched": len(toxicity_scores),
            "sensitive_topics_found": len([t for t in self.sensitive_topics if t.lower() in text.lower()])
        }
        
        return ToxicityResult(
            toxicity_score=overall_toxicity,
            toxicity_categories=toxicity_scores,
            flagged_content=flagged_content,
            confidence_score=confidence_score,
            analysis_details=analysis_details
        )
    
    def _pattern_based_flags(self, text: str) -> List[str]:
        """Get additional flags from pattern analysis."""
        flags = []
        
        # Check for excessive profanity (simplified)
        profanity_pattern = r"\b(damn|hell|shit|fuck|bitch|ass)\b"
        profanity_matches = len(re.findall(profanity_pattern, text, re.IGNORECASE))
        
        if profanity_matches > 3:  # More than 3 instances
            flags.append(f"Excessive profanity: {profanity_matches} instances")
        
        # Check for aggressive language
        aggressive_patterns = [
            r"\b(you\s+should|you\s+must|you\s+have\s+to)\b",
            r"\b(always|never|everyone|nobody)\s+(think|believe|say|know)\b"
        ]
        
        for pattern in aggressive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                flags.append(f"Aggressive language detected")
                break
        
        return flags
    
    def _calculate_confidence(self, toxicity_scores: Dict[str, float]) -> float:
        """Calculate confidence in toxicity detection."""
        if not toxicity_scores:
            return 0.0
        
        # Higher confidence when multiple categories agree
        high_scores = [score for score in toxicity_scores.values() if score >= 0.7]
        
        if len(high_scores) >= 2:
            return 0.9
        elif len(high_scores) == 1:
            return 0.8
        else:
            return 0.6
    
    async def batch_check_toxicity(self,
                                 texts: List[str],
                                 context: Optional[Dict[str, Any]] = None) -> List[ToxicityResult]:
        """Check toxicity for multiple texts in batch."""
        check_tasks = []
        
        for text in texts:
            task = self.check_toxicity(text, context)
            check_tasks.append(task)
        
        results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch toxicity check error: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_toxicity_summary(self, results: List[ToxicityResult]) -> Dict[str, Any]:
        """Get summary statistics for toxicity results."""
        if not results:
            return {"total_texts": 0}
        
        total_texts = len(results)
        toxic_texts = sum(1 for result in results if result.is_toxic(self.toxicity_threshold))
        
        # Category statistics
        category_stats = {}
        for result in results:
            for category, score in result.toxicity_categories.items():
                if category not in category_stats:
                    category_stats[category] = []
                category_stats[category].append(score)
        
        category_summary = {}
        for category, scores in category_stats.items():
            category_summary[category] = {
                "avg_score": sum(scores) / len(scores),
                "max_score": max(scores),
                "detection_rate": sum(1 for s in scores if s >= self.toxicity_threshold) / len(scores)
            }
        
        return {
            "total_texts": total_texts,
            "toxic_texts": toxic_texts,
            "toxicity_rate": toxic_texts / total_texts,
            "avg_toxicity_score": sum(result.toxicity_score for result in results) / total_texts,
            "category_statistics": category_summary
        }
    
    def get_checker_stats(self) -> Dict[str, Any]:
        """Get checker statistics."""
        return {
            "model_name": self.model_name,
            "toxicity_threshold": self.toxicity_threshold,
            "initialized": self.initialized,
            "model_available": self.toxicity_pipeline is not None,
            "toxicity_categories": self.toxicity_categories,
            "pattern_count": len(self.toxic_patterns),
            "sensitive_topics": self.sensitive_topics
        }
    
    def update_toxicity_threshold(self, threshold: float):
        """Update toxicity threshold."""
        self.toxicity_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"Toxicity threshold updated to {self.toxicity_threshold}")
    
    def add_toxic_pattern(self, pattern: str):
        """Add a new toxic pattern."""
        self.toxic_patterns.append(pattern)
        logger.info(f"Added toxic pattern: {pattern}")
    
    def remove_toxic_pattern(self, pattern: str):
        """Remove a toxic pattern."""
        if pattern in self.toxic_patterns:
            self.toxic_patterns.remove(pattern)
            logger.info(f"Removed toxic pattern: {pattern}")
    
    def add_sensitive_topic(self, topic: str):
        """Add a new sensitive topic."""
        self.sensitive_topics.append(topic)
        logger.info(f"Added sensitive topic: {topic}")
    
    def remove_sensitive_topic(self, topic: str):
        """Remove a sensitive topic."""
        if topic in self.sensitive_topics:
            self.sensitive_topics.remove(topic)
            logger.info(f"Removed sensitive topic: {topic}")
