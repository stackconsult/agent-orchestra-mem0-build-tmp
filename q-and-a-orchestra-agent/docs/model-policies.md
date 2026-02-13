# docs/model-policies.md
# Model Policies and Configuration Guide

## Overview

The Agent Orchestra Local LLM Router uses a sophisticated policy engine to automatically select the best model for each task. This document explains how to configure and customize model selection policies.

## Configuration Files

### models.yaml

The `config/models.yaml` file defines all available models and their capabilities:

```yaml
providers:
  ollama:
    type: local
    base_url: http://localhost:11434
    discover: true
    models:
      - id: llama3-8b-instruct
        display_name: "Llama 3 8B Instruct"
        capabilities: [general_qa, planning, summarization, tool_use_light]
        max_context: 8192
        quality_tier: medium
        latency_tier: medium
        cost_profile:
          type: local_cpu
          relative_cost: 1.0
```

#### Model Configuration Fields

- **id**: Unique model identifier
- **display_name**: Human-readable name
- **capabilities**: List of supported task types
- **max_context**: Maximum context window size
- **quality_tier**: very_high, high, medium, low
- **latency_tier**: low, medium, high
- **cost_profile**: Cost information (local_cpu or paid)

#### Provider Configuration Fields

- **type**: local or cloud
- **base_url**: API endpoint URL
- **base_url_env**: Environment variable for URL
- **api_key_env**: Environment variable for API key
- **discover**: Whether to auto-discover models (for local providers)

### policies.yaml

The `config/policies.yaml` file defines routing rules and preferences:

```yaml
routing:
  default_mode: local-preferred
  modes:
    local-only:
      allow_cloud: false
    local-preferred:
      allow_cloud: true
      cloud_usage_strategy: fallback_critical_only
```

#### Routing Modes

- **local-only**: Never use cloud models
- **local-preferred**: Prefer local models, use cloud as fallback
- **balanced**: Mix local and cloud based on policies
- **performance**: Prioritize quality and speed over cost

#### Task Overrides

Define specific preferences for different task types:

```yaml
task_overrides:
  routing:
    preferred_providers: [ollama]
    preferred_capabilities: [routing, classification, critic]
  planning:
    preferred_capabilities: [planning, multi_agent_orchestration]
```

#### Budget Configuration

Set spending limits and budget behavior:

```yaml
budgets:
  daily:
    total_usd: 10.0
    per_provider:
      openai: 5.0
      anthropic: 5.0
  monthly:
    total_usd: 150.0
```

## Task Types and Capabilities

### Supported Task Types

- **qa**: Question answering and general conversation
- **planning**: Complex planning and orchestration
- **routing**: Model routing and classification
- **coding**: Code generation and programming
- **summarization**: Text summarization
- **vision**: Image processing (future)
- **critic**: Critical analysis and evaluation

### Model Capabilities

Models can declare capabilities that map to task types:

- **general_qa**: Basic question answering
- **complex_qa**: Complex reasoning and analysis
- **planning**: Strategic planning and orchestration
- **multi_agent_orchestration**: Multi-agent system design
- **tool_use**: Function calling and tool usage
- **tool_use_light**: Limited tool support
- **routing**: Model routing decisions
- **classification**: Content classification
- **critic**: Critical evaluation
- **coding**: Code generation
- **summarization**: Text summarization

## Model Selection Algorithm

The policy engine uses a scoring algorithm to select the best model:

1. **Filter by capabilities**: Only models with required capabilities
2. **Filter by context**: Models must support required context size
3. **Filter by mode**: Respect routing mode (local-only, etc.)
4. **Score candidates**: Composite score based on weights
5. **Select best**: Choose lowest score (cost + quality + latency)

### Scoring Formula

```
score = w_cost * cost + w_quality * quality_rank + w_latency * latency_rank
```

- **cost**: Relative cost (local models are lowest)
- **quality_rank**: 1=very_high, 2=high, 3=medium, 4=low
- **latency_rank**: 1=low, 2=medium, 3=high

### Weight Configuration by Mode

```yaml
weights:
  local-preferred:
    cost: 0.6      # Prioritize low cost
    quality: 0.25  # Moderate quality preference
    latency: 0.15  # Lower latency priority
  performance:
    cost: 0.2      # Low cost priority
    quality: 0.6   # High quality preference
    latency: 0.2   # Moderate latency priority
```

## Environment Variables

Control behavior with environment variables:

```bash
# Routing mode
MODEL_ROUTING_MODE=local-preferred

# Budget limits
DAILY_BUDGET_LIMIT=10.0
MONTHLY_BUDGET_LIMIT=150.0

# Local model configuration
OLLAMA_BASE_URL=http://localhost:11434

# Cloud provider keys
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
GENERIC_OPENAI_API_KEY=your_key
GENERIC_OPENAI_BASE_URL=https://api.example.com/v1

# Dry run mode
DRY_RUN_MODE=false
```

## Adding New Models

### 1. Local Models (Ollama)

Add to `config/models.yaml`:

```yaml
providers:
  ollama:
    type: local
    base_url: http://localhost:11434
    discover: true  # Auto-discover available models
    models:
      - id: your-model-name
        display_name: "Your Model Display Name"
        capabilities: [general_qa, planning]
        max_context: 8192
        quality_tier: medium
        latency_tier: medium
        cost_profile:
          type: local_cpu
          relative_cost: 1.0
```

### 2. Cloud Models

Add new provider or extend existing:

```yaml
providers:
  your_provider:
    type: cloud
    base_url: https://api.yourprovider.com/v1
    api_key_env: YOUR_PROVIDER_API_KEY
    models:
      - id: your-model-id
        display_name: "Your Model"
        capabilities: [complex_qa, coding]
        max_context: 32768
        quality_tier: high
        latency_tier: medium
        cost_profile:
          type: paid
          currency: USD
          input_per_1k: 0.5
          output_per_1k: 1.5
```

### 3. Custom Provider Client

Create a new provider client in `providers/`:

```python
# providers/your_provider_client.py
from .base_client import BaseModelClient

class YourProviderClient(BaseModelClient):
    async def invoke(self, model_id, messages, tools=None, **kwargs):
        # Implementation here
        pass
    
    async def get_available_models(self):
        # Implementation here
        pass
    
    def health_check(self):
        # Implementation here
        pass
```

Then register in `core/model_router.py`:

```python
self.clients["your_provider"] = YourProviderClient()
```

## Monitoring and Telemetry

### Usage Tracking

The system tracks:
- Model usage by provider and model
- Success/failure rates
- Response times
- Cost estimates
- Routing decisions

### Cost Monitoring

Track spending per provider:
```python
# Get usage summary
summary = model_router.get_usage_summary()
print(f"Daily cost: ${summary['daily_cost']:.2f}")
print(f"Monthly cost: ${summary['monthly_cost']:.2f}")
```

### Health Monitoring

Check provider health:
```python
health = await model_router.health_check()
print(f"Provider health: {health}")
```

## Best Practices

### 1. Model Organization

- Group similar capabilities together
- Use consistent naming conventions
- Document model specialties and limitations

### 2. Cost Management

- Start with local-preferred mode
- Set reasonable budget limits
- Monitor usage regularly
- Use dry-run mode for testing

### 3. Performance Optimization

- Choose appropriate quality tiers
- Consider latency requirements
- Balance cost vs. performance needs
- Use fallback strategies

### 4. Security

- Never commit API keys
- Use environment variables for secrets
- Regularly rotate API keys
- Monitor for unusual usage

## Troubleshooting

### Common Issues

1. **Models not appearing**: Check provider configuration and API keys
2. **High costs**: Verify routing mode and budget settings
3. **Poor performance**: Adjust quality/latency weights
4. **Fallback failures**: Ensure multiple providers available

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG
```

Check model selection:
```python
# Plan without invoking
choice = model_router.plan(task_profile)
print(f"Would use: {choice.model.model_id}")
```

## Migration Guide

See `migration-from-paid-llm.md` for detailed migration instructions from existing Agent-orchestra-planner projects.
