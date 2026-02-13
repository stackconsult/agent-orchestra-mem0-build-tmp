# tests/test_providers.py
"""
Tests for provider client functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from providers.base_client import BaseModelClient
from providers.ollama_client import OllamaClient
from providers.openai_client import OpenAIClient
from providers.anthropic_client import AnthropicClient
from providers.generic_openai_client import GenericOpenAIClient


class TestBaseModelClient:
    """Test cases for BaseModelClient abstract class."""
    
    def test_abstract_methods(self):
        """Test that BaseModelClient requires implementation of abstract methods."""
        # Cannot instantiate abstract class
        with pytest.raises(TypeError):
            BaseModelClient()
        
        # Concrete implementation must implement all abstract methods
        class ConcreteClient(BaseModelClient):
            async def invoke(self, model_id, messages, tools=None, **kwargs):
                return {"content": "test"}
            
            async def get_available_models(self):
                return ["model1", "model2"]
            
            def health_check(self):
                return True
        
        client = ConcreteClient()
        assert client.health_check() is True


class TestOllamaClient:
    """Test cases for OllamaClient."""
    
    @pytest.fixture
    def client(self):
        """Create an OllamaClient instance for testing."""
        return OllamaClient(base_url="http://test:11434", timeout=30)
    
    @pytest.mark.asyncio
    async def test_invoke_success(self, client):
        """Test successful model invocation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Test response"}
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        
        with patch.object(client.client, 'post') as mock_post:
            mock_post.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            
            result = await client.invoke("llama3-8b", [{"role": "user", "content": "test"}])
            
            assert result["content"] == "Test response"
            assert result["model"] == "llama3-8b"
            assert result["provider"] == "ollama"
            assert result["usage"]["input_tokens"] == 10
            assert result["usage"]["output_tokens"] == 5
    
    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client):
        """Test model invocation with tools."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Test response"}
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        
        with patch.object(client.client, 'post') as mock_post:
            mock_post.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            
            tools = [{"type": "function", "function": {"name": "test_tool"}}]
            result = await client.invoke("llama3-8b", [{"role": "user", "content": "test"}], tools)
            
            # Ollama should ignore tools but still work
            assert result["content"] == "Test response"
    
    @pytest.mark.asyncio
    async def test_invoke_http_error(self, client):
        """Test handling of HTTP errors during invocation."""
        with patch.object(client.client, 'post') as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection error")
            
            with pytest.raises(httpx.HTTPError):
                await client.invoke("llama3-8b", [{"role": "user", "content": "test"}])
    
    @pytest.mark.asyncio
    async def test_get_available_models_success(self, client):
        """Test successful model discovery."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3-8b-instruct"},
                {"name": "mistral-7b-instruct"}
            ]
        }
        
        with patch.object(client.client, 'get') as mock_get:
            mock_get.return_value = mock_response
            mock_response.raise_for_status = MagicMock()
            
            models = await client.get_available_models()
            
            assert len(models) == 2
            assert "llama3-8b-instruct" in models
            assert "mistral-7b-instruct" in models
    
    @pytest.mark.asyncio
    async def test_get_available_models_error(self, client):
        """Test handling of errors during model discovery."""
        with patch.object(client.client, 'get') as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection error")
            
            models = await client.get_available_models()
            
            assert models == []
    
    def test_health_check_success(self, client):
        """Test successful health check."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            
            result = client.health_check()
            
            assert result is True
            mock_client.get.assert_called_with(f"{client.base_url}/api/tags")
    
    def test_health_check_failure(self, client):
        """Test failed health check."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.get.return_value = mock_response
            
            result = client.health_check()
            
            assert result is False
    
    def test_health_check_exception(self, client):
        """Test health check with exception."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            mock_client.get.side_effect = Exception("Connection error")
            
            result = client.health_check()
            
            assert result is False


class TestOpenAIClient:
    """Test cases for OpenAIClient."""
    
    @pytest.fixture
    def client(self):
        """Create an OpenAIClient instance for testing."""
        return OpenAIClient(api_key="test_key", timeout=30)
    
    @pytest.mark.asyncio
    async def test_invoke_success(self, client):
        """Test successful model invocation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        
        with patch.object(client.client, 'chat') as mock_chat:
            mock_chat.completions.create.return_value = mock_response
            
            result = await client.invoke("gpt-4", [{"role": "user", "content": "test"}])
            
            assert result["content"] == "Test response"
            assert result["model"] == "gpt-4"
            assert result["provider"] == "openai"
            assert result["usage"]["input_tokens"] == 10
            assert result["usage"]["output_tokens"] == 5
    
    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client):
        """Test model invocation with tools."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        
        # Mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "test_function"
        mock_tool_call.function.arguments = '{"arg": "value"}'
        
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        
        with patch.object(client.client, 'chat') as mock_chat:
            mock_chat.completions.create.return_value = mock_response
            
            tools = [{"type": "function", "function": {"name": "test_tool"}}]
            result = await client.invoke("gpt-4", [{"role": "user", "content": "test"}], tools)
            
            assert result["content"] == "Test response"
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["id"] == "call_123"
    
    @pytest.mark.asyncio
    async def test_get_available_models_success(self, client):
        """Test successful model listing."""
        mock_model1 = MagicMock()
        mock_model1.id = "gpt-4"
        mock_model2 = MagicMock()
        mock_model2.id = "gpt-3.5-turbo"
        
        with patch.object(client.client, 'models') as mock_models:
            mock_models.list.return_value.data = [mock_model1, mock_model2]
            
            models = await client.get_available_models()
            
            assert len(models) == 2
            assert "gpt-4" in models
            assert "gpt-3.5-turbo" in models
    
    @pytest.mark.asyncio
    async def test_get_available_models_no_key(self, client):
        """Test model listing without API key."""
        client.api_key = None
        
        models = await client.get_available_models()
        
        assert models == []
    
    def test_health_check_no_key(self, client):
        """Test health check without API key."""
        client.api_key = None
        
        result = client.health_check()
        
        assert result is False


class TestAnthropicClient:
    """Test cases for AnthropicClient."""
    
    @pytest.fixture
    def client(self):
        """Create an AnthropicClient instance for testing."""
        return AnthropicClient(api_key="test_key", timeout=30)
    
    @pytest.mark.asyncio
    async def test_invoke_success(self, client):
        """Test successful model invocation."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].type = "text"
        mock_response.content[0].text = "Test response"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        
        with patch.object(client.client, 'messages') as mock_messages:
            mock_messages.create.return_value = mock_response
            
            result = await client.invoke("claude-3-sonnet", [{"role": "user", "content": "test"}])
            
            assert result["content"] == "Test response"
            assert result["model"] == "claude-3-sonnet"
            assert result["provider"] == "anthropic"
            assert result["usage"]["input_tokens"] == 10
            assert result["usage"]["output_tokens"] == 5
    
    @pytest.mark.asyncio
    async def test_invoke_with_system_message(self, client):
        """Test model invocation with system message."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].type = "text"
        mock_response.content[0].text = "Test response"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        
        with patch.object(client.client, 'messages') as mock_messages:
            mock_messages.create.return_value = mock_response
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "test"}
            ]
            
            result = await client.invoke("claude-3-sonnet", messages)
            
            assert result["content"] == "Test response"
            # Check that system parameter was passed
            mock_messages.create.assert_called_once()
            call_args = mock_messages.create.call_args
            assert "system" in call_args.kwargs
    
    @pytest.mark.asyncio
    async def test_invoke_with_tools(self, client):
        """Test model invocation with tools."""
        mock_response = MagicMock()
        
        # Mock text content
        mock_text = MagicMock()
        mock_text.type = "text"
        mock_text.text = "Test response"
        
        # Mock tool use content
        mock_tool = MagicMock()
        mock_tool.type = "tool_use"
        mock_tool.id = "tool_123"
        mock_tool.name = "test_function"
        mock_tool.input = '{"arg": "value"}'
        
        mock_response.content = [mock_text, mock_tool]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        
        with patch.object(client.client, 'messages') as mock_messages:
            mock_messages.create.return_value = mock_response
            
            tools = [{"type": "function", "function": {"name": "test_tool"}}]
            result = await client.invoke("claude-3-sonnet", [{"role": "user", "content": "test"}], tools)
            
            assert result["content"] == "Test response"
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["id"] == "tool_123"
    
    @pytest.mark.asyncio
    async def test_get_available_models(self, client):
        """Test getting available models (returns known models)."""
        models = await client.get_available_models()
        
        assert len(models) > 0
        assert any("claude-3" in model for model in models)
    
    def test_health_check_with_key(self, client):
        """Test health check with API key."""
        result = client.health_check()
        
        assert result is True
    
    def test_health_check_no_key(self, client):
        """Test health check without API key."""
        client.api_key = None
        
        result = client.health_check()
        
        assert result is False


class TestGenericOpenAIClient:
    """Test cases for GenericOpenAIClient."""
    
    @pytest.fixture
    def client(self):
        """Create a GenericOpenAIClient instance for testing."""
        return GenericOpenAIClient(
            api_key="test_key",
            base_url="https://api.example.com/v1",
            timeout=30
        )
    
    @pytest.mark.asyncio
    async def test_invoke_success(self, client):
        """Test successful model invocation."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        
        with patch.object(client.client, 'chat') as mock_chat:
            mock_chat.completions.create.return_value = mock_response
            
            result = await client.invoke("custom-model", [{"role": "user", "content": "test"}])
            
            assert result["content"] == "Test response"
            assert result["model"] == "custom-model"
            assert result["provider"] == "generic_openai"
    
    @pytest.mark.asyncio
    async def test_get_available_models_no_config(self, client):
        """Test model listing without configuration."""
        client.api_key = None
        client.base_url = None
        
        models = await client.get_available_models()
        
        assert models == []
    
    def test_health_check_no_config(self, client):
        """Test health check without configuration."""
        client.api_key = None
        client.base_url = None
        
        result = client.health_check()
        
        assert result is False
