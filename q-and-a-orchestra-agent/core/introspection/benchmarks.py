"""
Model Benchmark Suite

Provides standardized testing for model discovery including
performance, quality, and capability assessment.
"""

import asyncio
import time
import tiktoken
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .model_profile import BenchmarkResult, ModelProfile


@dataclass
class BenchmarkPrompt:
    """Standardized benchmark prompt."""
    name: str
    prompt: str
    task_type: str
    expected_response: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7


class BenchmarkSuite:
    """Standardized benchmark suite for model evaluation."""
    
    def __init__(self):
        """Initialize benchmark suite with test prompts."""
        self.test_prompts = self._get_standard_prompts()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer as reference
    
    def _get_standard_prompts(self) -> List[BenchmarkPrompt]:
        """Get standardized benchmark prompts for capability assessment."""
        return [
            # Basic chat capability
            BenchmarkPrompt(
                name="basic_chat",
                prompt="Hello! How are you today?",
                task_type="chat",
                expected_response=None,
                max_tokens=100
            ),
            
            # QA accuracy
            BenchmarkPrompt(
                name="qa_accuracy",
                prompt="What is the capital of France? Please give a brief answer.",
                task_type="qa",
                expected_response="Paris",
                max_tokens=50
            ),
            
            # Code generation
            BenchmarkPrompt(
                name="code_generation",
                prompt="Write a Python function that checks if a number is prime.",
                task_type="coding",
                max_tokens=200
            ),
            
            # Reasoning
            BenchmarkPrompt(
                name="logical_reasoning",
                prompt="If all cats are animals, and some animals are pets, can we conclude that some cats are pets? Explain your reasoning.",
                task_type="reasoning",
                max_tokens=150
            ),
            
            # Math problem
            BenchmarkPrompt(
                name="math_problem",
                prompt="What is 15% of 240? Show your work.",
                task_type="math",
                expected_response="36",
                max_tokens=100
            ),
            
            # Summarization
            BenchmarkPrompt(
                name="summarization",
                prompt="Summarize this text in one sentence: The solar system consists of the Sun and the objects that orbit it, including eight planets, dwarf planets, moons, asteroids, and comets.",
                task_type="summarization",
                max_tokens=50
            ),
            
            # Creative writing
            BenchmarkPrompt(
                name="creative_writing",
                prompt="Write a short poem about the ocean.",
                task_type="creative",
                max_tokens=100
            ),
            
            # Function calling (JSON mode test)
            BenchmarkPrompt(
                name="json_mode",
                prompt='Respond with JSON only: {"status": "ok", "message": "test successful"}',
                task_type="structured_output",
                expected_response='{"status": "ok", "message": "test successful"}',
                max_tokens=50
            )
        ]
    
    async def run_benchmark_suite(self, model_client: Any, model_profile: ModelProfile) -> List[BenchmarkResult]:
        """Run complete benchmark suite on a model."""
        results = []
        
        for prompt_def in self.test_prompts:
            try:
                result = await self._run_single_benchmark(model_client, model_profile, prompt_def)
                results.append(result)
            except Exception as e:
                # Create failed result
                result = BenchmarkResult(
                    test_name=prompt_def.name,
                    prompt=prompt_def.prompt,
                    expected_response=prompt_def.expected_response,
                    actual_response="",
                    latency_ms=0,
                    tokens_per_second=0,
                    quality_score=0.0,
                    cost_per_1k_tokens=model_profile.estimated_cost_input_per_1k,
                    success=False,
                    error_message=str(e)
                )
                results.append(result)
        
        return results
    
    async def _run_single_benchmark(self, model_client: Any, model_profile: ModelProfile, prompt_def: BenchmarkPrompt) -> BenchmarkResult:
        """Run a single benchmark test."""
        # Tokenize prompt for cost calculation
        input_tokens = len(self.tokenizer.encode(prompt_def.prompt))
        
        # Start timing
        start_time = time.time()
        
        try:
            # Call model (implementation depends on provider)
            response = await self._call_model(model_client, prompt_def, model_profile)
            
            # End timing
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            # Tokenize response
            output_tokens = len(self.tokenizer.encode(response))
            total_tokens = input_tokens + output_tokens
            
            # Calculate tokens per second
            tokens_per_second = output_tokens / (latency_ms / 1000) if latency_ms > 0 else 0
            
            # Calculate cost
            cost = (input_tokens / 1000) * model_profile.estimated_cost_input_per_1k + \
                   (output_tokens / 1000) * model_profile.estimated_cost_output_per_1k
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(prompt_def, response)
            
            return BenchmarkResult(
                test_name=prompt_def.name,
                prompt=prompt_def.prompt,
                expected_response=prompt_def.expected_response,
                actual_response=response,
                latency_ms=latency_ms,
                tokens_per_second=tokens_per_second,
                quality_score=quality_score,
                cost_per_1k_tokens=cost / total_tokens * 1000 if total_tokens > 0 else 0,
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            return BenchmarkResult(
                test_name=prompt_def.name,
                prompt=prompt_def.prompt,
                expected_response=prompt_def.expected_response,
                actual_response="",
                latency_ms=latency_ms,
                tokens_per_second=0,
                quality_score=0.0,
                cost_per_1k_tokens=model_profile.estimated_cost_input_per_1k,
                success=False,
                error_message=str(e)
            )
    
    async def _call_model(self, model_client: Any, prompt_def: BenchmarkPrompt, model_profile: ModelProfile) -> str:
        """Call model based on provider type."""
        # This will be implemented by specific provider clients
        # For now, return a placeholder
        if hasattr(model_client, 'generate'):
            return await model_client.generate(
                prompt=prompt_def.prompt,
                max_tokens=prompt_def.max_tokens,
                temperature=prompt_def.temperature
            )
        elif hasattr(model_client, 'chat'):
            return await model_client.chat(
                messages=[{"role": "user", "content": prompt_def.prompt}],
                max_tokens=prompt_def.max_tokens,
                temperature=prompt_def.temperature
            )
        else:
            raise ValueError(f"Model client {model_client} does not have supported interface")
    
    def _calculate_quality_score(self, prompt_def: BenchmarkPrompt, response: str) -> float:
        """Calculate quality score for benchmark response."""
        if not response or response.strip() == "":
            return 0.0
        
        score = 0.5  # Base score for giving any response
        
        # Length appropriateness
        if len(response.strip()) > 10:
            score += 0.1
        
        # Expected response check
        if prompt_def.expected_response:
            if prompt_def.expected_response.lower() in response.lower():
                score += 0.3
            elif any(word in response.lower() for word in prompt_def.expected_response.lower().split()):
                score += 0.15
        
        # Task-specific scoring
        if prompt_def.task_type == "qa":
            score += self._score_qa_response(response)
        elif prompt_def.task_type == "coding":
            score += self._score_coding_response(response)
        elif prompt_def.task_type == "math":
            score += self._score_math_response(response, prompt_def.expected_response)
        elif prompt_def.task_type == "structured_output":
            score += self._score_json_response(response)
        
        return min(score, 1.0)
    
    def _score_qa_response(self, response: str) -> float:
        """Score QA response quality."""
        # Check for confidence indicators
        confidence_indicators = ["is", "are", "the", "a", "an"]
        if any(indicator in response.lower() for indicator in confidence_indicators):
            return 0.2
        return 0.1
    
    def _score_coding_response(self, response: str) -> float:
        """Score code generation quality."""
        # Check for Python function indicators
        code_indicators = ["def ", "function", "return", "if ", "for ", "while "]
        if any(indicator in response for indicator in code_indicators):
            return 0.2
        return 0.05
    
    def _score_math_response(self, response: str, expected: str) -> float:
        """Score math problem response."""
        try:
            # Extract numbers from response
            import re
            numbers = re.findall(r'\d+\.?\d*', response)
            if numbers and expected:
                if numbers[0] in expected:
                    return 0.3
        except:
            pass
        return 0.1
    
    def _score_json_response(self, response: str) -> float:
        """Score JSON output quality."""
        try:
            import json
            json.loads(response)
            return 0.3
        except:
            return 0.05
