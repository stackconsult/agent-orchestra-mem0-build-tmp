# API Documentation with Context Engineering

## Overview

Agent Orchestra provides a RESTful API for interacting with AI agents with intelligent model routing and 6-Layer Context Engineering. The API is organized into versioned endpoints to ensure backward compatibility.

## Base URL

```text
Development: http://localhost:8000
Production: https://your-domain.com
```

## Authentication

The API uses Bearer token authentication with multi-tenant support:

```http
Authorization: Bearer <your-jwt-token>
X-Tenant-ID: <your-tenant-id>
X-User-ID: <your-user-id>
X-User-Roles: <comma-separated-roles>
```

### Obtaining a Token

```http
POST /auth/login
Content-Type: application/json

{
  "username": "your-username",
  "password": "your-password",
  "tenant_id": "your-tenant-id"
}
```

Response:

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "tenant_id": "your-tenant-id"
}
```

## Core Endpoints

### 1. Health Check

Check system health and component status including context engineering.

```http
GET /health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "version": "2.1.0",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "model_router": "healthy",
    "agents": "healthy",
    "context_engineering": "healthy",
    "semantic_cache": "healthy"
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

### 2. Chat Endpoint with Context Engineering (v2)

Primary endpoint for interacting with the agent orchestra using 6-Layer Context Engineering.

```http
POST /v2/chat
Content-Type: application/json
Authorization: Bearer <token>
X-Tenant-ID: <tenant-id>

{
  "messages": [
    {
      "role": "user",
      "content": "Analyze my React project and suggest improvements"
    }
  ],
  "task_type": "repo_analysis",
  "team_id": "optional-team-id",
  "project_id": "optional-project-id",
  "repository_path": "/path/to/repo",
  "session_id": "optional-session-id",
  "enable_cache": true,
  "enable_validation": true,
  "max_tokens": 4000,
  "temperature": 0.7,
  "metadata": {
    "priority": "medium"
  },
  "context_overrides": {
    "override_user_preferences": {
      "detail_level": "expert"
    },
    "override_rules": {
      "hard_walls": {
        "allow_live_exec": false
      }
    }
  }
}
```

Response:

```json
{
  "response": "Based on my analysis of your React project...",
  "model_id": "claude-3-5-sonnet",
  "provider": "anthropic",
  "routing_metadata": {
    "provider": "anthropic",
    "model": "claude-3-5-sonnet",
    "reasons": ["Best fit for analysis tasks", "High accuracy"],
    "score": 0.95,
    "context_id": "ctx_123456789",
    "routing_factors": {
      "intent": "repo_analysis",
      "expertise": "intermediate",
      "environment": "production",
      "compliance_required": true
    }
  },
  "cache_hit": false,
  "validation_passed": true,
  "cost_usd": 0.025,
  "quality_score": 0.92,
  "tenant_id": "tenant-123",
  "context_id": "ctx_123456789",
  "context_token_count": 3456,
  "context_processing_time_ms": 45.2,
  "latency_ms": 1250.5
}
```

### 3. Context Debug Endpoint

Debug and inspect how context is built for a given message.

```http
GET /v2/context/debug?message=Analyze my code&task_type=repo_analysis
Authorization: Bearer <token>
```

Response:

```json
{
  "context_envelope": {
    "context_id": "ctx_debug_123",
    "user": {
      "user_id": "user-456",
      "tenant_id": "tenant-123",
      "roles": ["developer"],
      "expertise_level": "intermediate",
      "preferences": {
        "tone": "technical",
        "detail_level": "medium"
      }
    },
    "intent": {
      "primary_intent": "repo_analysis",
      "task_type": "repo_analysis",
      "success_criteria": "Deliver actionable insights with next steps",
      "confidence_score": 0.95
    },
    "domain": {
      "repo_path": "/path/to/repo",
      "repo_summary": "React TypeScript project with Redux",
      "key_components": {
        "frontend": "React 18",
        "state": "Redux Toolkit",
        "build": "Vite"
      }
    },
    "rules": {
      "soft_walls": {
        "brand_voice": "sharp, practical",
        "style": "short paragraphs"
      },
      "hard_walls": {
        "forbidden_actions": ["execute_live_code"],
        "pii_handling": "never log secrets"
      }
    },
    "environment": {
      "environment": "production",
      "model_routing_mode": "local-preferred",
      "feature_flags": {
        "semantic_cache": true,
        "context_engineering_v2": true
      }
    },
    "exposition": {
      "narrative": "User: ID user-456, Expertise: intermediate\nIntent: repo_analysis...",
      "structured": {
        "user_id": "user-456",
        "primary_intent": "repo_analysis",
        "environment": "production"
      }
    }
  },
  "token_usage": {
    "total": 3456,
    "by_layer": {
      "user": 234,
      "intent": 156,
      "domain": 1234,
      "rules": 890,
      "environment": 123,
      "exposition": 819
    }
  }
}
```

## Context Engineering Features

### 6 Layers of Context

1. **User Layer**: Captures identity, roles, expertise, preferences, and history
2. **Intent Layer**: Detects what job the user is hiring the system to do
3. **Domain Layer**: Understands workspace entities, repos, and relationships
4. **Rules Layer**: Enforces hard walls (compliance) and soft walls (style)
5. **Environment Layer**: Tracks system state, load, and deployment context
6. **Exposition Layer**: Fuses all layers into optimized LLM payload

### Context Overrides

Temporarily override context for specific requests:

```json
{
  "context_overrides": {
    "override_user_preferences": {
      "detail_level": "expert",
      "tone": "formal"
    },
    "override_intent": {
      "primary_intent": "security_analysis"
    },
    "override_domain": {
      "repo_path": "/different/repo"
    },
    "override_rules": {
      "hard_walls": {
        "allow_live_exec": true
      }
    }
  }
}
```

### Intent Types

The system automatically detects intent from messages:

- `architecture_design`: System design and architecture
- `repo_analysis`: Codebase analysis and review
- `implementation`: Code implementation and features
- `troubleshooting`: Bug fixing and debugging
- `security_analysis`: Security review and vulnerability assessment
- `performance_optimization`: Performance analysis and improvement
- `documentation`: Documentation generation
- `planning`: Project planning and roadmapping

### Context-Aware Routing

Model routing considers:

- User expertise level
- Intent type and criticality
- Compliance requirements
- System load and environment
- Tenant policies
- Token budget constraints

## Advanced Features

### Semantic Caching

Context-aware caching that considers:

```http
POST /v2/chat
{
  "messages": [{"role": "user", "content": "How do I implement auth?"}],
  "task_type": "implementation",
  "enable_cache": true
}
```

Cache key includes:

- Message content
- Detected intent
- User expertise level
- Context hash

### Response Validation

Validate responses against rules:

```json
{
  "validation_passed": true,
  "quality_score": 0.92,
  "validation_details": {
    "rules_compliant": true,
    "hard_walls_passed": true,
    "soft_walls_score": 0.88
  }
}
```

### Budget Management

Track costs per tenant/project:

```json
{
  "cost_usd": 0.025,
  "budget_remaining": 97.475,
  "budget_warnings": [],
  "cost_breakdown": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "model_cost_per_token": 0.000015
  }
}
```

## Error Handling

### Context Engineering Errors

```json
{
  "error": "ContextBuildingError",
  "message": "Failed to build domain context",
  "details": {
    "layer": "domain",
    "source": "repo_analyzer",
    "error": "Repository not found at /path/to/repo",
    "fallback_used": true
  }
}
```

### Compliance Violations

```json
{
  "error": "ComplianceViolation",
  "message": "Request violates hard wall constraints",
  "violations": [
    {
      "rule": "forbidden_actions",
      "value": "execute_live_code",
      "severity": "high"
    }
  ]
}
```

## Rate Limiting

Context-aware rate limiting:

```http
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1640995200
X-RateLimit-Policy: tenant-based
```

Limits vary by:

- Tenant tier
- User role
- Intent type
- System load

## SDK Examples

### Python SDK

```python
from orchestra_client import OrchestraClient

client = OrchestraClient(
    base_url="http://localhost:8000",
    token="your-token",
    tenant_id="your-tenant"
)

# Simple chat with context
response = await client.chat(
    message="Analyze my project",
    repository_path="/path/to/repo",
    task_type="repo_analysis"
)

# With context overrides
response = await client.chat(
    message="Implement feature X",
    context_overrides={
        "override_user_preferences": {"detail_level": "expert"}
    }
)

# Debug context
context = await client.debug_context(
    message="Design a microservice",
    task_type="architecture_design"
)
print(context.token_usage)
```

### JavaScript SDK

```javascript
import { OrchestraClient } from '@orchestra/js-sdk';

const client = new OrchestraClient({
  baseURL: 'http://localhost:8000',
  token: 'your-token',
  tenantId: 'your-tenant'
});

// Chat with context
const response = await client.chat({
  messages: [{ role: 'user', content: 'Analyze my code' }],
  repositoryPath: '/path/to/repo',
  taskType: 'repo_analysis'
});

console.log(response.contextId);
console.log(response.routingMetadata.routingFactors);
```

## Best Practices

1. **Provide Rich Context**: Include repository paths and project IDs when available
2. **Use Appropriate Task Types**: Helps the system select the right agents
3. **Leverage Context Overrides**: For temporary preference changes
4. **Monitor Token Usage**: Use debug endpoint to optimize context
5. **Cache When Appropriate**: Enable caching for repeated queries
6. **Handle Validation Failures**: Check validation_passed in responses
7. **Respect Rate Limits**: Implement exponential backoff

## Migration from v1

To migrate from v1 to v2 with context engineering:

1. Update endpoint from `/v1/chat` to `/v2/chat`
2. Change request format:
   - `message` → `messages` array
   - Add `task_type` for better routing
3. Handle new response fields:
   - `context_id`
   - `context_token_count`
   - `validation_passed`
4. Update error handling for context-specific errors

## Changelog

### v2.1.0 - Context Engineering Release

- Added 6-Layer Context Engineering
- Context-aware model routing
- Intent detection and classification
- Compliance rule enforcement
- Context debugging endpoint
- Enhanced caching with context awareness

### v2.0.0 - Enterprise Features

- Multi-tenancy support
- Budget management
- Audit logging
- Semantic caching
- Advanced policy engine
