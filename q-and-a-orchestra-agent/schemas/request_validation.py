"""
Request Validation Schemas

Pydantic models for comprehensive input validation and sanitization.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
import re
import logging

logger = logging.getLogger(__name__)

class TaskProfileRequest(BaseModel):
    """Validated task profile input."""
    task_type: str = Field(..., pattern="^(qa|planning|routing|coding|summarization|vision|critic)$")
    criticality: str = Field("medium", pattern="^(low|medium|high)$")
    latency_sensitivity: str = Field("medium", pattern="^(low|medium|high)$")
    context_size: int = Field(0, ge=0, le=200000)  # Max 200K tokens
    tool_use_required: bool = False
    budget_sensitivity: str = Field("medium", pattern="^(low|medium|high)$")
    
    @field_validator('context_size')
    @classmethod
    def validate_context_size(cls, v):
        if v < 0:
            raise ValueError("context_size must be non-negative")
        if v > 200000:
            raise ValueError("context_size exceeds maximum of 200000 tokens")
        return v

class MessageInput(BaseModel):
    """Validated LLM message input."""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=50000)
    
    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v):
        # Remove potentially dangerous characters
        v = v.strip()
        
        # Check for injection attempts
        dangerous_patterns = [
            '<script', 'javascript:', 'onerror=', 'onclick=', 
            'onload=', 'eval(', 'alert(', 'document.cookie'
        ]
        
        content_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                logger.warning(f"Potentially dangerous content detected: {pattern}")
                raise ValueError(f"Content contains potentially dangerous pattern: {pattern}")
        
        return v

class InvokeModelRequest(BaseModel):
    """Validated model invocation request."""
    task: TaskProfileRequest
    messages: List[MessageInput] = Field(..., min_length=1, max_length=100)
    tools: Optional[List[Dict[str, Any]]] = None
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(4000, ge=1, le=32000)
    
    @field_validator('messages')
    @classmethod
    def validate_messages(cls, v):
        if len(v) > 100:
            raise ValueError("Maximum 100 messages allowed per request")
        
        # Validate message sequence
        if v[0].role != "system":
            raise ValueError("First message must be from 'system' role")
        
        # Check for alternating pattern after system message
        for i in range(1, len(v)):
            if i % 2 == 1 and v[i].role != "user":
                raise ValueError(f"Message {i+1} should be from 'user' role")
            elif i % 2 == 0 and v[i].role != "assistant":
                raise ValueError(f"Message {i+1} should be from 'assistant' role")
        
        return v
    
    @field_validator('tools')
    @classmethod
    def validate_tools(cls, v):
        if v is None:
            return v
        
        if len(v) > 20:
            raise ValueError("Maximum 20 tools allowed per request")
        
        for tool in v:
            if not isinstance(tool, dict):
                raise ValueError("Each tool must be a dictionary")
            
            required_fields = ['name', 'description']
            for field in required_fields:
                if field not in tool:
                    raise ValueError(f"Tool missing required field: {field}")
        
        return v

class SessionCreateRequest(BaseModel):
    """Validated session creation request."""
    user_id: Optional[str] = Field(None, min_length=1, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    
    @field_validator('user_id')
    @classmethod
    def sanitize_user_id(cls, v):
        if v is None:
            return v
        
        # Remove potentially dangerous characters
        v = re.sub(r'[<>"\'&]', '', v)
        
        if len(v) > 100:
            raise ValueError("user_id too long")
        
        return v

class UserInputRequest(BaseModel):
    """Validated user input request."""
    session_id: str = Field(..., min_length=1, max_length=100)
    user_input: str = Field(..., min_length=1, max_length=10000)
    input_type: str = Field("text", pattern="^(text|file|image)$")
    
    @field_validator('user_input')
    @classmethod
    def sanitize_user_input(cls, v):
        v = v.strip()
        
        # Basic XSS prevention
        if '<script' in v.lower():
            raise ValueError("Input contains potentially dangerous content")
        
        return v

class RefinementRequest(BaseModel):
    """Validated refinement request."""
    session_id: str = Field(..., min_length=1, max_length=100)
    refinement_type: str = Field(..., pattern="^(architecture|implementation|cost|security|performance)$")
    description: str = Field(..., min_length=1, max_length=5000)
    
    @field_validator('description')
    @classmethod
    def sanitize_description(cls, v):
        v = v.strip()
        
        # Check for injection attempts
        if any(pattern in v.lower() for pattern in ['<script', 'javascript:', 'eval(']):
            raise ValueError("Description contains potentially dangerous content")
        
        return v
