# API Documentation

## Overview

Agent Orchestra provides a RESTful API for interacting with AI agents and managing model routing. The API is organized into versioned endpoints to ensure backward compatibility.

## Base URL

```text
Development: http://localhost:8000
Production: https://your-domain.com
```

## Authentication

The API uses Bearer token authentication:

```http
Authorization: Bearer <your-jwt-token>
```

### Obtaining a Token

```http
POST /auth/login
Content-Type: application/json

{
  "username": "your-username",
  "password": "your-password"
}
```

Response:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## Core Endpoints

### 1. Health Check

Check system health and component status.

```http
GET /health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "2.0.0",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "model_router": "healthy",
    "agents": "healthy"
  },
  "models": {
    "ollama": {
      "llama3-8b-instruct": "available",
      "qwen2.5-3b-instruct": "available"
    },
    "anthropic": {
      "claude-3-5-sonnet": "available"
    }
  }
}
```

### 2. Chat Endpoint (v2)

Primary endpoint for interacting with the agent orchestra.

```http
POST /v2/chat
Content-Type: application/json
Authorization: Bearer <token>

{
  "message": "Analyze my React project and suggest improvements",
  "session_id": "optional-session-id",
  "context": {
    "repository_path": "/path/to/repo",
    "task_type": "analysis",
    "priority": "medium"
  },
  "options": {
    "stream": false,
    "include_reasoning": true,
    "model_preference": "local-first"
  }
}
```

Response:

```json
{
  "session_id": "sess_123456789",
  "message_id": "msg_987654321",
  "response": {
    "content": "I've analyzed your React project. Here are the key findings...",
    "agent_used": "repository_analyzer",
    "model_used": "llama3-8b-instruct",
    "confidence": 0.92,
    "reasoning": "The project structure suggests a standard React setup..."
  },
  "routing_metadata": {
    "provider": "ollama",
    "model": "llama3-8b-instruct",
    "score": 0.95,
    "reasons": ["local_model_available", "task_complexity_low"],
    "fallback": false
  },
  "usage": {
    "input_tokens": 150,
    "output_tokens": 300,
    "cost": 0.0002
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### Streaming Response

Enable streaming for real-time responses:

```http
POST /v2/chat
Content-Type: application/json

{
  "message": "Help me implement a new feature",
  "options": {
    "stream": true
  }
}
```

Response (Server-Sent Events):

```text
data: {"type": "start", "session_id": "sess_123"}

data: {"type": "token", "content": "I'll"}

data: {"type": "token", "content": " help"}

data: {"type": "end", "usage": {"tokens": 150}}
```

### 3. List Models

Get available models and their capabilities.

```http
GET /v2/models
Authorization: Bearer <token>
```

Response:

```json
{
  "models": [
    {
      "id": "llama3-8b-instruct",
      "provider": "ollama",
      "type": "local",
      "capabilities": ["chat", "completion", "code_generation"],
      "context_window": 8192,
      "cost_per_1k_tokens": {
        "input": 0.0,
        "output": 0.0
      },
      "performance": {
        "avg_latency_ms": 500,
        "success_rate": 0.98
      }
    },
    {
      "id": "claude-3-5-sonnet",
      "provider": "anthropic",
      "type": "cloud",
      "capabilities": ["chat", "completion", "reasoning", "tool_use"],
      "context_window": 200000,
      "cost_per_1k_tokens": {
        "input": 0.003,
        "output": 0.015
      },
      "performance": {
        "avg_latency_ms": 800,
        "success_rate": 0.99
      }
    }
  ],
  "total_models": 2,
  "routing_mode": "local-preferred"
}
```

### 4. Analytics Dashboard

Get usage analytics and metrics.

```http
GET /v2/analytics/dashboard?start_date=2024-01-01&end_date=2024-01-31
Authorization: Bearer <token>
```

Response:

```json
{
  "period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "usage": {
    "total_requests": 1250,
    "total_tokens": 125000,
    "total_cost": 15.50,
    "avg_response_time_ms": 650
  },
  "by_model": {
    "llama3-8b-instruct": {
      "requests": 800,
      "tokens": 80000,
      "cost": 0.0,
      "success_rate": 0.98
    },
    "claude-3-5-sonnet": {
      "requests": 450,
      "tokens": 45000,
      "cost": 15.50,
      "success_rate": 0.99
    }
  },
  "by_agent": {
    "repository_analyzer": 300,
    "requirements_extractor": 250,
    "architecture_designer": 200,
    "implementation_planner": 300,
    "validator": 200
  },
  "errors": [
    {
      "type": "rate_limit",
      "count": 5,
      "percentage": 0.4
    }
  ]
}
```

### 5. Budget Status

Monitor budget usage and limits.

```http
GET /v2/budget/status
Authorization: Bearer <token>
```

Response:

```json
{
  "current_period": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "limits": {
    "monthly_budget": 100.0,
    "daily_budget": 10.0,
    "per_model_budget": {
      "claude-3-5-sonnet": 50.0
    }
  },
  "usage": {
    "monthly_spent": 15.50,
    "daily_spent": 2.30,
    "remaining_monthly": 84.50,
    "remaining_daily": 7.70
  },
  "alerts": [
    {
      "type": "warning",
      "message": "Daily budget 77% used",
      "threshold": 0.75
    }
  ]
}
```

### 6. Model Discovery

Trigger discovery of available models.

```http
POST /v2/discovery/run
Authorization: Bearer <token>
```

Response:

```json
{
  "task_id": "task_789012",
  "status": "started",
  "message": "Model discovery initiated"
}
```

Check discovery status:

```http
GET /v2/discovery/status/{task_id}
```

### 7. Recommendations

Get optimization recommendations.

```http
GET /v2/recommendations
Authorization: Bearer <token>
```

Response:

```json
{
  "recommendations": [
    {
      "type": "cost_optimization",
      "priority": "high",
      "title": "Use local models for simple queries",
      "description": "30% of your queries could use local models",
      "potential_savings": "$5.00/month"
    },
    {
      "type": "performance",
      "priority": "medium",
      "title": "Enable semantic caching",
      "description": "Caching could reduce latency by 40%",
      "implementation": "Set CACHE_ENABLED=true"
    }
  ]
}
```

## Agent-Specific Endpoints

### Repository Analyzer

Analyze a codebase repository:

```http
POST /v2/agents/repository-analyzer/analyze
Content-Type: application/json

{
  "repository_path": "/path/to/repo",
  "analysis_type": "full",
  "include_patterns": ["*.py", "*.js", "*.ts"],
  "exclude_patterns": ["node_modules/*", "__pycache__/*"]
}
```

### Requirements Extractor

Extract requirements from text:

```http
POST /v2/agents/requirements-extractor/extract
Content-Type: application/json

{
  "text": "User story: As a user, I want to reset my password...",
  "format": "user_stories",
  "include_acceptance_criteria": true
}
```

### Architecture Designer

Design system architecture:

```http
POST /v2/agents/architecture-designer/design
Content-Type: application/json

{
  "requirements": ["scalable", "microservices", "real-time"],
  "constraints": ["budget_limit", "tech_stack"],
  "preferences": ["cloud_native", "serverless"]
}
```

## Error Handling

The API uses standard HTTP status codes:

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 429 | Rate Limited |
| 500 | Internal Server Error |

Error response format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid request parameters",
    "details": {
      "field": "message",
      "issue": "Required field missing"
    }
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "request_id": "req_123456"
}
```

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| /v2/chat | 10 requests | 1 minute |
| /v2/models | 20 requests | 1 minute |
| /v2/analytics/* | 5 requests | 1 minute |
| /auth/* | 5 requests | 1 minute |

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640995200
```

## SDK Examples

### Python

```python
import requests

# Initialize client
client = AgentOrchestraClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)

# Chat with agents
response = client.chat(
    message="Analyze my project",
    context={"repository_path": "/path/to/repo"}
)

print(response.response.content)
```

### JavaScript

```javascript
import { AgentOrchestraClient } from '@agent-orchestra/sdk';

const client = new AgentOrchestraClient({
  baseURL: 'http://localhost:8000',
  token: 'your-jwt-token'
});

const response = await client.chat({
  message: 'Analyze my project',
  context: { repositoryPath: '/path/to/repo' }
});

console.log(response.response.content);
```

### cURL

```bash
# Chat with agents
curl -X POST http://localhost:8000/v2/chat \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze my project",
    "context": {"repository_path": "/path/to/repo"}
  }'
```

## Webhooks

Configure webhooks for real-time notifications:

```http
POST /v2/webhooks
Content-Type: application/json

{
  "url": "https://your-app.com/webhooks",
  "events": ["chat.completed", "budget.alert"],
  "secret": "webhook-secret"
}
```

Webhook payload:

```json
{
  "event": "chat.completed",
  "data": {
    "session_id": "sess_123",
    "cost": 0.05,
    "model": "llama3-8b-instruct"
  },
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Pagination

List endpoints support pagination:

```http
GET /v2/analytics/requests?page=1&limit=50&sort=timestamp
```

Response:

```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 1250,
    "pages": 25,
    "has_next": true,
    "has_prev": false
  }
}
```

## Support

For API support:

- Documentation: <https://docs.agent-orchestra.com>
- Issues: <https://github.com/stackconsult/agent-orchestra/issues>
- Email: <api-support@agent-orchestra.com>
