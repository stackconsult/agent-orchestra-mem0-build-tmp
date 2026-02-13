# providers/anthropic_client.py
import os
import logging
from typing import List, Dict, Any, Optional

from anthropic import AsyncAnthropic

from .base_client import BaseModelClient

logger = logging.getLogger(__name__)


class AnthropicClient(BaseModelClient):
    """Client for Anthropic Claude API."""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("Anthropic API key not provided, client will not work")
        
        self.client = AsyncAnthropic(api_key=self.api_key, timeout=timeout)
    
    async def invoke(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
        ) -> Dict[str, Any]:
        """Invoke an Anthropic Claude model."""
        try:
            # Convert messages to Anthropic format
            anthropic_messages = []
            system_message = None
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] in ["user", "assistant"]:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Prepare parameters
            params = {
                "model": model_id,
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 1000),
                "temperature": kwargs.get("temperature", 0.7),
            }
            
            if system_message:
                params["system"] = system_message
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
            
            response = await self.client.messages.create(**params)
            
            # Extract content
            content = ""
            tool_calls = []
            
            for content_block in response.content:
                if content_block.type == "text":
                    content += content_block.text
                elif content_block.type == "tool_use":
                    tool_calls.append({
                        "id": content_block.id,
                        "type": "tool_use",
                        "function": {
                            "name": content_block.name,
                            "arguments": content_block.input
                        }
                    })
            
            return {
                "content": content,
                "tool_calls": tool_calls,
                "model": model_id,
                "provider": "anthropic",
                "usage": {
                    "input_tokens": response.usage.input_tokens if response.usage else 0,
                    "output_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
                },
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error invoking Anthropic model {model_id}: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get list of available Anthropic models."""
        # Anthropic doesn't have a public models list endpoint
        # Return known models
        known_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
        
        logger.info(f"Returning {len(known_models)} known Anthropic models")
        return known_models
    
    def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            if not self.api_key:
                return False
            
            # Simple check - try to get account info (this might not be available)
            # For now, just check if we have an API key
            return bool(self.api_key)
                
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False
    
    async def close(self):
        """Close the Anthropic client."""
        # Anthropic client doesn't have an explicit close method
        pass
