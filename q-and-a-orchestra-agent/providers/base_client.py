# providers/base_client.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseModelClient(ABC):
    """Abstract base class for all model providers."""
    
    @abstractmethod
    async def invoke(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Invoke a model with the given messages and optional tools.
        
        Args:
            model_id: The model identifier
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool definitions
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Response dictionary containing model output and metadata
        """
        pass
    
    @abstractmethod
    async def get_available_models(self) -> List[str]:
        """
        Get list of available model IDs from this provider.
        
        Returns:
            List of model identifiers
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
