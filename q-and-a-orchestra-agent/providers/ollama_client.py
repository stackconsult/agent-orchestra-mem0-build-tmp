# providers/ollama_client.py
import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from .base_client import BaseModelClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseModelClient):
    """Client for Ollama local models."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 60):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def invoke(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Invoke an Ollama model."""
        try:
            # Ollama API format
            payload = {
                "model": model_id,
                "messages": messages,
                "stream": False,
            }
            
            # Add optional parameters
            if "temperature" in kwargs:
                payload["options"] = payload.get("options", {})
                payload["options"]["temperature"] = kwargs["temperature"]
            
            if "max_tokens" in kwargs:
                payload["options"] = payload.get("options", {})
                payload["options"]["num_predict"] = kwargs["max_tokens"]
            
            # Note: Ollama has limited tool support, this is a basic implementation
            if tools:
                logger.warning("Tool support in Ollama is limited, tools will be ignored")
            
            response = await self.client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Normalize response format
            return {
                "content": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                "model": model_id,
                "provider": "ollama",
                "usage": {
                    "input_tokens": result.get("usage", {}).get("prompt_tokens", 0),
                    "output_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                },
                "raw_response": result
            }
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error invoking Ollama model {model_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error invoking Ollama model {model_id}: {e}")
            raise
    
    async def get_available_models(self) -> List[str]:
        """Get list of available Ollama models."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            
            logger.info(f"Discovered {len(models)} Ollama models: {models}")
            return models
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting Ollama models: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting Ollama models: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            # Simple synchronous check using httpx
            import httpx
            client = httpx.Client(timeout=5)
            response = client.get(f"{self.base_url}/api/tags")
            client.close()
            
            if response.status_code == 200:
                logger.debug("Ollama health check passed")
                return True
            else:
                logger.warning(f"Ollama health check failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
