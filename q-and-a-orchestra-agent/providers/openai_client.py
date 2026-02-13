# providers/openai_client.py
import os
import logging
from typing import List, Dict, Any, Optional

import httpx
from openai import AsyncOpenAI

from .base_client import BaseModelClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseModelClient):
    """Client for OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 60):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or "https://api.openai.com/v1"
        self.timeout = timeout
        
        if not self.api_key:
            logger.warning("OpenAI API key not provided, client will not work")
        
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout
        )
    
    async def invoke(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Invoke an OpenAI model."""
        try:
            # Prepare parameters
            params = {
                "model": model_id,
                "messages": messages,
                "max_tokens": kwargs.get("max_tokens", 1000),
                "temperature": kwargs.get("temperature", 0.7),
            }
            
            # Add tools if provided
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(**params)
            
            # Extract content
            content = response.choices[0].message.content or ""
            
            # Handle tool calls if any
            tool_calls = []
            if response.choices[0].message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in response.choices[0].message.tool_calls
                ]
            
            return {
                "content": content,
                "tool_calls": tool_calls,
                "model": model_id,
                "provider": "openai",
                "usage": {
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0
                },
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error invoking OpenAI model {model_id}: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get list of available OpenAI models."""
        try:
            if not self.api_key:
                logger.warning("Cannot get OpenAI models: no API key")
                return []
            
            models = await self.client.models.list()
            model_ids = [model.id for model in models.data]
            
            logger.info(f"Discovered {len(model_ids)} OpenAI models")
            return model_ids
            
        except Exception as e:
            logger.error(f"Error getting OpenAI models: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            if not self.api_key:
                return False
            
            # Simple check - try to list models
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                models = loop.run_until_complete(self.client.models.list())
                return True
            except:
                return False
                
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
    
    async def close(self):
        """Close the OpenAI client."""
        await self.client.close()
