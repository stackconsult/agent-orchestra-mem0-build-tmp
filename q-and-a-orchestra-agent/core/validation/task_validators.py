"""
Task Validators

Task-specific validation logic for different types of responses
including code, math, summaries, and other specialized tasks.
"""

import asyncio
import logging
import re
import ast
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TaskValidationResult:
    """Result of task-specific validation."""
    passed: bool
    score: float  # 0-1
    issues: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "score": self.score,
            "issues": self.issues,
            "metadata": self.metadata
        }


class TaskValidator(ABC):
    """Abstract base class for task validators."""
    
    @abstractmethod
    async def validate(self,
                      response: str,
                      prompt: Optional[str] = None,
                      context: Optional[Dict[str, Any]] = None) -> TaskValidationResult:
        """Validate response for specific task type."""
        pass
    
    @abstractmethod
    def get_task_type(self) -> str:
        """Get the task type this validator handles."""
        pass


class CodeValidator(TaskValidator):
    """Validator for code generation tasks."""
    
    def __init__(self):
        """Initialize code validator."""
        self.supported_languages = {
            'python', 'javascript', 'java', 'cpp', 'c', 'go', 'rust',
            'sql', 'html', 'css', 'json', 'xml', 'yaml'
        }
    
    async def validate(self,
                      response: str,
                      prompt: Optional[str] = None,
                      context: Optional[Dict[str, Any]] = None) -> TaskValidationResult:
        """Validate code response."""
        issues = []
        score = 1.0
        
        # Extract code blocks
        code_blocks = self._extract_code_blocks(response)
        
        if not code_blocks:
            issues.append({
                "severity": "medium",
                "description": "No code blocks found in response",
                "suggestion": "Include code in proper code blocks"
            })
            score -= 0.3
        
        # Validate each code block
        for i, (language, code) in enumerate(code_blocks):
            block_score, block_issues = await self._validate_code_block(language, code, i)
            score = min(score, block_score)
            issues.extend(block_issues)
        
        # Check for security issues
        security_issues = self._check_security_issues(code_blocks)
        issues.extend(security_issues)
        if security_issues:
            score -= 0.2
        
        # Check for code quality
        quality_issues = self._check_code_quality(code_blocks)
        issues.extend(quality_issues)
        if quality_issues:
            score -= 0.1
        
        passed = score >= 0.7 and not any(
            issue["severity"] == "critical" for issue in issues
        )
        
        metadata = {
            "code_blocks_count": len(code_blocks),
            "languages_detected": list(set(lang for lang, _ in code_blocks)),
            "security_issues_count": len(security_issues),
            "quality_issues_count": len(quality_issues)
        }
        
        return TaskValidationResult(
            passed=passed,
            score=max(0, score),
            issues=issues,
            metadata=metadata
        )
    
    def get_task_type(self) -> str:
        """Get task type."""
        return "coding"
    
    def _extract_code_blocks(self, text: str) -> List[Tuple[str, str]]:
        """Extract code blocks from text."""
        code_blocks = []
        
        # Markdown code blocks
        pattern = r"```(\w*)\n?(.*?)\n?```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        for language, code in matches:
            if not language:
                # Try to detect language
                language = self._detect_language(code)
            code_blocks.append((language.lower(), code.strip()))
        
        # Inline code blocks
        inline_pattern = r"`([^`\n]+)`"
        inline_matches = re.findall(inline_pattern, text)
        
        for code in inline_matches:
            if len(code) > 10:  # Only include substantial inline code
                language = self._detect_language(code)
                code_blocks.append((language, code))
        
        return code_blocks
    
    def _detect_language(self, code: str) -> str:
        """Detect programming language from code."""
        code_lower = code.lower()
        
        # Simple language detection based on keywords
        if any(keyword in code_lower for keyword in ['def ', 'import ', 'from ', 'class ', '__init__']):
            return 'python'
        elif any(keyword in code for keyword in ['function ', 'const ', 'let ', 'var ', '=>']):
            return 'javascript'
        elif any(keyword in code for keyword in ['public class ', 'private ', 'protected ', 'import java']):
            return 'java'
        elif any(keyword in code for keyword in ['#include', 'int main', 'printf', 'scanf']):
            return 'c'
        elif any(keyword in code for keyword in ['#include', 'std::', 'cout', 'cin']):
            return 'cpp'
        elif any(keyword in code for keyword in ['SELECT ', 'FROM ', 'WHERE ', 'INSERT ']):
            return 'sql'
        elif any(keyword in code for keyword in ['<!DOCTYPE', '<html>', '<div>', '<script>']):
            return 'html'
        elif any(keyword in code for keyword in ['{', '}', 'margin:', 'padding:', 'color:']):
            return 'css'
        
        return 'unknown'
    
    async def _validate_code_block(self,
                                 language: str,
                                 code: str,
                                 block_index: int) -> Tuple[float, List[Dict[str, Any]]]:
        """Validate individual code block."""
        issues = []
        score = 1.0
        
        # Check syntax
        syntax_valid, syntax_errors = self._check_syntax(language, code)
        if not syntax_valid:
            issues.extend(syntax_errors)
            score -= 0.4
        
        # Check for common errors
        common_errors = self._check_common_errors(language, code)
        issues.extend(common_errors)
        if common_errors:
            score -= 0.2
        
        # Check code structure
        structure_issues = self._check_code_structure(language, code)
        issues.extend(structure_issues)
        if structure_issues:
            score -= 0.1
        
        return max(0, score), issues
    
    def _check_syntax(self, language: str, code: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """Check code syntax."""
        errors = []
        
        try:
            if language == 'python':
                ast.parse(code)
            elif language in ['javascript', 'json']:
                # Basic syntax check for JS/JSON
                if '{' in code and '}' in code:
                    pass  # Basic bracket matching
            # Add more language-specific syntax checks
        except SyntaxError as e:
            errors.append({
                "severity": "high",
                "description": f"Syntax error: {str(e)}",
                "suggestion": "Fix syntax errors in the code"
            })
        except Exception as e:
            errors.append({
                "severity": "medium",
                "description": f"Code parsing error: {str(e)}",
                "suggestion": "Check code format and structure"
            })
        
        return len(errors) == 0, errors
    
    def _check_common_errors(self, language: str, code: str) -> List[Dict[str, Any]]:
        """Check for common coding errors."""
        errors = []
        
        if language == 'python':
            # Check for common Python errors
            if 'print ' in code and '(' not in code.split('print ')[1][:10]:
                errors.append({
                    "severity": "medium",
                    "description": "Python 2 print syntax detected",
                    "suggestion": "Use print() function for Python 3"
                })
        
        elif language == 'javascript':
            # Check for common JS errors
            if 'var ' in code:
                errors.append({
                    "severity": "low",
                    "description": "Consider using const/let instead of var",
                    "suggestion": "Use const or let for better scoping"
                })
        
        return errors
    
    def _check_code_structure(self, language: str, code: str) -> List[Dict[str, Any]]:
        """Check code structure and best practices."""
        issues = []
        
        # Check for proper indentation
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith(' '):
                # Check if this should be indented
                if i > 0 and lines[i-1].strip().endswith(':'):
                    issues.append({
                        "severity": "low",
                        "description": f"Missing indentation on line {i+1}",
                        "suggestion": "Add proper indentation"
                    })
        
        return issues
    
    def _check_security_issues(self, code_blocks: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Check for security issues in code."""
        issues = []
        
        dangerous_patterns = {
            'eval(': "Use of eval() can be dangerous",
            'exec(': "Use of exec() can be dangerous",
            'system(': "Direct system command execution",
            'subprocess.call': "System command execution",
            'os.system': "System command execution",
            'shell=True': "Shell injection risk",
            'password': "Hardcoded password detected",  # nosec: B105
            'secret': "Hardcoded secret detected",  # nosec: B105
            'token': "Hardcoded token detected"  # nosec: B105
        }
        
        for language, code in code_blocks:
            for pattern, description in dangerous_patterns.items():
                if pattern in code:
                    severity = "high" if any(danger in pattern for danger in ['eval', 'exec', 'system']) else "medium"
                    issues.append({
                        "severity": severity,
                        "description": description,
                        "suggestion": "Review and remove dangerous code patterns"
                    })
        
        return issues
    
    def _check_code_quality(self, code_blocks: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Check code quality issues."""
        issues = []
        
        for language, code in code_blocks:
            # Check for very long lines
            lines = code.split('\n')
            for i, line in enumerate(lines):
                if len(line) > 120:
                    issues.append({
                        "severity": "low",
                        "description": f"Very long line ({len(line)} characters) at line {i+1}",
                        "suggestion": "Break long lines for better readability"
                    })
            
            # Check for missing comments (for substantial code)
            if len(code) > 100 and '#' not in code and '//' not in code and '/*' not in code:
                issues.append({
                    "severity": "low",
                    "description": "Missing comments in substantial code block",
                    "suggestion": "Add comments to explain complex code"
                })
        
        return issues


class MathValidator(TaskValidator):
    """Validator for mathematical problem solving."""
    
    async def validate(self,
                      response: str,
                      prompt: Optional[str] = None,
                      context: Optional[Dict[str, Any]] = None) -> TaskValidationResult:
        """Validate math response."""
        issues = []
        score = 1.0
        
        # Extract mathematical expressions
        math_expressions = self._extract_math_expressions(response)
        
        if not math_expressions:
            issues.append({
                "severity": "medium",
                "description": "No mathematical expressions found",
                "suggestion": "Include mathematical calculations or formulas"
            })
            score -= 0.3
        
        # Validate calculations
        for expr in math_expressions:
            calc_score, calc_issues = self._validate_calculation(expr)
            score = min(score, calc_score)
            issues.extend(calc_issues)
        
        # Check for step-by-step explanation
        if not self._has_step_by_step_explanation(response):
            issues.append({
                "severity": "low",
                "description": "Missing step-by-step explanation",
                "suggestion": "Include detailed steps for better understanding"
            })
            score -= 0.1
        
        passed = score >= 0.7
        
        metadata = {
            "math_expressions_count": len(math_expressions),
            "has_step_by_step": self._has_step_by_step_explanation(response)
        }
        
        return TaskValidationResult(
            passed=passed,
            score=max(0, score),
            issues=issues,
            metadata=metadata
        )
    
    def get_task_type(self) -> str:
        """Get task type."""
        return "math"
    
    def _extract_math_expressions(self, text: str) -> List[str]:
        """Extract mathematical expressions from text."""
        expressions = []
        
        # Look for common math patterns
        patterns = [
            r'\b\d+\s*[+\-*/]\s*\d+',  # Simple arithmetic
            r'\b\d+\s*\^\s*\d+',      # Exponents
            r'\b\d+\s*%\s*\d+',       # Modulo
            r'\b\d+\s*\*\s*\d+\s*\*\s*\d+',  # Cubes
            r'\b\(\s*[^)]+\s*\)',      # Parentheses
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches)
        
        return expressions
    
    def _validate_calculation(self, expression: str) -> Tuple[float, List[Dict[str, Any]]]:
        """Validate mathematical calculation."""
        issues = []
        score = 1.0
        
        try:
            # Safe evaluation (basic arithmetic only)
            if any(op in expression for op in ['+', '-', '*', '/', '%', '^']):
                # Replace ^ with ** for Python
                expr_safe = expression.replace('^', '**')
                
                # Only allow safe characters and use ast.literal_eval for safety
                if re.match(r'^[0-9+\-*/().\s^%]+$', expr_safe):
                    import ast
                    import operator
                    try:
                        # Use safe arithmetic evaluation instead of eval
                        def safe_eval(expr):
                            """Safely evaluate arithmetic expressions."""
                            allowed_operators = {
                                ast.Add: operator.add,
                                ast.Sub: operator.sub,
                                ast.Mult: operator.mul,
                                ast.Div: operator.truediv,
                                ast.Pow: operator.pow,
                                ast.Mod: operator.mod,
                                ast.USub: operator.neg,
                                ast.UAdd: operator.pos,
                            }
                            
                            node = ast.parse(expr, mode='eval')
                            def eval_node(node):
                                if isinstance(node, ast.Expression):
                                    return eval_node(node.body)
                                elif isinstance(node, ast.Num):  # Python < 3.8
                                    return node.n
                                elif isinstance(node, ast.Constant):  # Python >= 3.8
                                    return node.value
                                elif isinstance(node, ast.BinOp):
                                    left = eval_node(node.left)
                                    right = eval_node(node.right)
                                    op_type = type(node.op)
                                    if op_type in allowed_operators:
                                        return allowed_operators[op_type](left, right)
                                    else:
                                        raise ValueError(f"Unsupported operator: {op_type}")
                                elif isinstance(node, ast.UnaryOp):
                                    operand = eval_node(node.operand)
                                    op_type = type(node.op)
                                    if op_type in allowed_operators:
                                        return allowed_operators[op_type](operand)
                                    else:
                                        raise ValueError(f"Unsupported unary operator: {op_type}")
                                else:
                                    raise ValueError(f"Unsupported expression: {type(node)}")
                            
                            return eval_node(node)
                        
                        result = safe_eval(expr_safe)
                        
                        # Check if result is reasonable
                        if abs(result) > 1000000:
                            issues.append({
                                "severity": "low",
                                "description": "Very large result, check calculation",
                                "suggestion": "Verify the calculation is correct"
                            })
                            score -= 0.1
                    except (SyntaxError, NameError, TypeError, ValueError):
                        issues.append({
                            "severity": "medium",
                            "category": "security",
                            "issue": "Invalid mathematical expression",
                            "suggestion": "Use valid mathematical expressions only"
                        })
                        score -= 0.3
                else:
                    issues.append({
                        "severity": "medium",
                        "description": "Potentially unsafe mathematical expression",
                        "suggestion": "Use only basic arithmetic operations"
                    })
                    score -= 0.3
        except Exception as e:
            issues.append({
                "severity": "high",
                "description": f"Invalid mathematical expression: {str(e)}",
                "suggestion": "Check mathematical syntax"
            })
            score -= 0.5
        
        return max(0, score), issues
    
    def _has_step_by_step_explanation(self, text: str) -> bool:
        """Check if response has step-by-step explanation."""
        step_indicators = [
            'step', 'first', 'second', 'third', 'next', 'then',
            'finally', 'lastly', '1.', '2.', '3.'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in step_indicators)


class SummaryValidator(TaskValidator):
    """Validator for text summarization tasks."""
    
    async def validate(self,
                      response: str,
                      prompt: Optional[str] = None,
                      context: Optional[Dict[str, Any]] = None) -> TaskValidationResult:
        """Validate summary response."""
        issues = []
        score = 1.0
        
        # Check summary length
        word_count = len(response.split())
        if word_count < 20:
            issues.append({
                "severity": "medium",
                "description": "Summary too short",
                "suggestion": "Provide a more comprehensive summary"
            })
            score -= 0.3
        elif word_count > 500:
            issues.append({
                "severity": "low",
                "description": "Summary too long",
                "suggestion": "Make summary more concise"
            })
            score -= 0.1
        
        # Check for coherence
        coherence_score = self._check_coherence(response)
        if coherence_score < 0.7:
            issues.append({
                "severity": "medium",
                "description": "Summary lacks coherence",
                "suggestion": "Improve flow and connections between ideas"
            })
            score -= 0.2
        
        # Check for main points
        if not self._has_main_points(response):
            issues.append({
                "severity": "low",
                "description": "Summary may miss key points",
                "suggestion": "Ensure main ideas are captured"
            })
            score -= 0.1
        
        passed = score >= 0.7
        
        metadata = {
            "word_count": word_count,
            "coherence_score": coherence_score,
            "has_main_points": self._has_main_points(response)
        }
        
        return TaskValidationResult(
            passed=passed,
            score=max(0, score),
            issues=issues,
            metadata=metadata
        )
    
    def get_task_type(self) -> str:
        """Get task type."""
        return "summarization"
    
    def _check_coherence(self, text: str) -> float:
        """Check text coherence."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 2:
            return 0.5
        
        # Simple coherence check based on sentence connections
        coherence_score = 0.8  # Base score
        
        # Check for transition words
        transitions = ['however', 'therefore', 'furthermore', 'moreover', 'additionally']
        transition_count = sum(1 for sentence in sentences 
                             if any(trans in sentence.lower() for trans in transitions))
        
        if transition_count > 0:
            coherence_score += 0.1 * min(transition_count, 3)
        
        return min(coherence_score, 1.0)
    
    def _has_main_points(self, text: str) -> bool:
        """Check if summary captures main points."""
        # Simple heuristic: look for topic sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Check for sentences that start with important indicators
        important_starters = ['the main', 'the primary', 'key', 'important', 'significant']
        
        return any(
            any(starter in sentence.lower() for starter in important_starters)
            for sentence in sentences
        )


class TaskValidatorRegistry:
    """Registry for task validators."""
    
    def __init__(self):
        """Initialize validator registry."""
        self.validators: Dict[str, TaskValidator] = {}
        self._register_default_validators()
    
    def _register_default_validators(self):
        """Register default validators."""
        self.register_validator(CodeValidator())
        self.register_validator(MathValidator())
        self.register_validator(SummaryValidator())
    
    def register_validator(self, validator: TaskValidator):
        """Register a task validator."""
        task_type = validator.get_task_type()
        self.validators[task_type] = validator
        logger.info(f"Registered validator for task type: {task_type}")
    
    def get_validator(self, task_type: str) -> Optional[TaskValidator]:
        """Get validator for task type."""
        return self.validators.get(task_type)
    
    def list_supported_tasks(self) -> List[str]:
        """List supported task types."""
        return list(self.validators.keys())
    
    def validate_task(self,
                     task_type: str,
                     response: str,
                     prompt: Optional[str] = None,
                     context: Optional[Dict[str, Any]] = None) -> TaskValidationResult:
        """Validate response for specific task type."""
        validator = self.get_validator(task_type)
        
        if not validator:
            return TaskValidationResult(
                passed=False,
                score=0.0,
                issues=[{
                    "severity": "high",
                    "description": f"No validator available for task type: {task_type}",
                    "suggestion": "Add a validator for this task type"
                }],
                metadata={"task_type": task_type}
            )
        
        return asyncio.create_task(
            validator.validate(response, prompt, context)
        )
    
    async def batch_validate(self,
                           tasks: List[Tuple[str, str, Optional[str]]],
                           context: Optional[Dict[str, Any]] = None) -> List[TaskValidationResult]:
        """Validate multiple tasks in batch."""
        validation_tasks = []
        
        for task_type, response, prompt in tasks:
            task = self.validate_task(task_type, response, prompt, context)
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
