# Migration Guide: From Paid LLM to Local-First Router

## Overview

This guide helps you migrate existing Agent-orchestra-planner projects to use the new local-first LLM router. The migration preserves all existing functionality while adding cost savings and local model support.

## Migration Benefits

- **Cost Reduction**: Up to 90% cost savings with local models
- **Privacy**: Keep data local when possible
- **Reliability**: No API rate limits or downtime
- **Flexibility**: Mix local and cloud models as needed
- **Observability**: Better tracking and cost management

## Pre-Migration Checklist

### 1. Assess Current Usage

Review your existing project to understand:

```python
# Find all direct LLM calls
grep -r "anthropic" src/
grep -r "openai" src/
grep -r "claude" src/
```

### 2. Identify Dependencies

Check which LLM providers you're using:

- Anthropic Claude
- OpenAI GPT
- Other providers

### 3. Estimate Requirements

- Daily/monthly usage volume
- Critical vs. non-critical tasks
- Budget constraints
- Performance requirements

## Migration Steps

### Step 1: Install Dependencies

Add new dependencies to your `requirements.txt`:

```txt
# Existing dependencies...
fastapi==0.104.1
anthropic==0.7.8
openai==1.3.8

# New dependencies for model router
pyyaml==6.0.1
# Ollama uses HTTP, no specific client needed
```

### Step 2: Add Configuration Files

Create `config/models.yaml`:

```yaml
providers:
  ollama:
    type: local
    base_url: http://localhost:11434
    discover: true
    models:
      - id: llama3-8b-instruct
        display_name: "Llama 3 8B Instruct"
        capabilities: [general_qa, planning, summarization]
        max_context: 8192
        quality_tier: medium
        latency_tier: medium
        cost_profile:
          type: local_cpu
          relative_cost: 1.0
  
  anthropic:
    type: cloud
    api_key_env: ANTHROPIC_API_KEY
    models:
      - id: claude-3-5-sonnet
        display_name: "Claude 3.5 Sonnet"
        capabilities: [planning, multi_agent_orchestration, complex_qa]
        max_context: 200000
        quality_tier: very_high
        latency_tier: medium
        cost_profile:
          type: paid
          currency: USD
          input_per_1k: 3.0
          output_per_1k: 15.0
```

Create `config/policies.yaml`:

```yaml
routing:
  default_mode: local-preferred
  modes:
    local-only:
      allow_cloud: false
    local-preferred:
      allow_cloud: true
      cloud_usage_strategy: fallback_critical_only
    balanced:
      allow_cloud: true
      cloud_usage_strategy: balanced
    performance:
      allow_cloud: true
      cloud_usage_strategy: aggressive
  
  weights:
    local-preferred:
      cost: 0.6
      quality: 0.25
      latency: 0.15
    balanced:
      cost: 0.4
      quality: 0.4
      latency: 0.2
    performance:
      cost: 0.2
      quality: 0.6
      latency: 0.2

task_overrides:
  planning:
    preferred_capabilities: [planning, multi_agent_orchestration]
  qa:
    preferred_capabilities: [general_qa, complex_qa]
  routing:
    preferred_providers: [ollama]
    preferred_capabilities: [routing, classification]

budgets:
  daily:
    total_usd: 10.0
    per_provider:
      anthropic: 5.0
      openai: 5.0
  monthly:
    total_usd: 150.0
```

### Step 3: Update Environment Variables

Add to your `.env` file:

```bash
# Model routing
MODEL_ROUTING_MODE=local-preferred
DAILY_BUDGET_LIMIT=10.0
MONTHLY_BUDGET_LIMIT=150.0

# Local models
OLLAMA_BASE_URL=http://localhost:11434

# Existing cloud keys (keep for fallback)
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

# Dry run mode for testing
DRY_RUN_MODE=false
```

### Step 4: Update Agent Classes

#### Before (Direct Anthropic Usage)

```python
from anthropic import AsyncAnthropic

class MyAgent:
    def __init__(self):
        self.anthropic = AsyncAnthropic(api_key="your_key")
    
    async def process(self, text):
        response = await self.anthropic.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[{"role": "user", "content": text}]
        )
        return response.content[0].text
```

#### After (Model Router Usage)

```python
from core.model_router import ModelRouter
from core.task_profiles import TaskProfile

class MyAgent:
    def __init__(self):
        self.model_router = ModelRouter()
    
    async def process(self, text):
        task_profile = TaskProfile(
            task_type="qa",
            criticality="medium",
            latency_sensitivity="medium",
            context_size=len(text),
            tool_use_required=False,
            budget_sensitivity="medium"
        )
        
        messages = [{"role": "user", "content": text}]
        
        result = await self.model_router.select_and_invoke(
            task_profile, messages, max_tokens=1000
        )
        
        return result["content"]
```

### Step 5: Update Application Initialization

#### Before

```python
from anthropic import AsyncAnthropic

anthropic_client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
orchestrator = OrchestraOrchestrator(anthropic_client, redis_url)
```

#### After

```python
from core.model_router import ModelRouter

model_router = ModelRouter(dry_run=os.getenv("DRY_RUN_MODE", "false").lower() == "true")
orchestrator = OrchestraOrchestrator(model_router, redis_url)
```

### Step 6: Update Orchestrator

Modify your orchestrator to accept ModelRouter instead of direct LLM clients:

```python
class OrchestraOrchestrator:
    def __init__(self, model_router: ModelRouter, redis_url: str):
        self.model_router = model_router
        self.redis_url = redis_url
        # Initialize agents with model_router instead of anthropic_client
        self.agent = MyAgent(model_router)
```

## Testing the Migration

### 1. Dry Run Mode

Test without making actual API calls:

```bash
DRY_RUN_MODE=true python main.py
```

### 2. Model Selection Planning

Test model selection logic:

```python
# Test which model would be selected
task = TaskProfile(task_type="planning", criticality="high")
choice = model_router.plan(task)
print(f"Would use: {choice.model.model_id} ({choice.model.provider_name})")
```

### 3. Health Checks

Verify all providers are accessible:

```python
health = await model_router.health_check()
print(f"Provider health: {health}")
```

### 4. Cost Estimates

Check potential costs:

```python
# Get available models and costs
models = model_router.get_available_models()
print(f"Available models: {models}")
```

## Gradual Migration Strategy

### Phase 1: Parallel Operation

Keep existing code running alongside new router:

```python
class HybridAgent:
    def __init__(self):
        self.legacy_anthropic = AsyncAnthropic(api_key=key)
        self.model_router = ModelRouter()
        self.use_router = os.getenv("USE_MODEL_ROUTER", "false").lower() == "true"
    
    async def process(self, text):
        if self.use_router:
            return await self._process_with_router(text)
        else:
            return await self._process_legacy(text)
```

### Phase 2: Feature Flags

Use feature flags to control migration:

```python
USE_ROUTER_FOR_QA=os.getenv("USE_ROUTER_FOR_QA", "true")
USE_ROUTER_FOR_PLANNING=os.getenv("USE_ROUTER_FOR_PLANNING", "false")
```

### Phase 3: Full Migration

Switch completely to router once confident:

```python
# Set environment variable
MODEL_ROUTING_MODE=local-preferred
USE_MODEL_ROUTER=true
```

## Common Migration Patterns

### 1. Simple Text Processing

```python
# Before
response = await anthropic.messages.create(model="claude-3-sonnet", messages=messages)

# After
task = TaskProfile(task_type="qa", criticality="medium")
result = await model_router.select_and_invoke(task, messages)
```

### 2. Tool Usage

```python
# Before
response = await anthropic.messages.create(
    model="claude-3-sonnet",
    messages=messages,
    tools=tools
)

# After
task = TaskProfile(task_type="routing", tool_use_required=True)
result = await model_router.select_and_invoke(task, messages, tools=tools)
```

### 3. Complex Planning

```python
# Before
response = await anthropic.messages.create(
    model="claude-3-sonnet",
    max_tokens=4000,
    messages=messages
)

# After
task = TaskProfile(
    task_type="planning",
    criticality="high",
    context_size=4000,
    budget_sensitivity="low"  # Allow cloud for critical tasks
)
result = await model_router.select_and_invoke(task, messages, max_tokens=4000)
```

## Post-Migration Optimization

### 1. Monitor Usage

Track model selection and costs:

```python
summary = model_router.get_usage_summary()
print(f"Daily cost: ${summary['daily_cost']:.2f}")
print(f"Cloud vs Local ratio: {summary['cost_by_provider']}")
```

### 2. Adjust Policies

Fine-tune routing based on actual usage:

```yaml
# Update policies.yaml based on usage patterns
task_overrides:
  planning:
    preferred_capabilities: [planning, multi_agent_orchestration]
    # Add more specific preferences based on your needs
```

### 3. Add Local Models

Install and configure additional local models:

```bash
# Install more Ollama models
ollama pull mistral-7b-instruct
ollama pull qwen2.5-3b-instruct

# Add to models.yaml
```

## Troubleshooting Migration Issues

### Issue 1: Model Selection Not Working

**Symptoms**: Always selecting same model or no model

**Solutions**:

1. Check `config/models.yaml` syntax
2. Verify model capabilities match task types
3. Check routing mode configuration
4. Review policy weights

### Issue 2: High Cloud Costs

**Symptoms**: Unexpected cloud usage

**Solutions**:

1. Set `MODEL_ROUTING_MODE=local-only`
2. Adjust budget limits
3. Review task overrides
4. Check model capabilities

### Issue 3: Performance Degradation

**Symptoms**: Slower responses than before

**Solutions**:

1. Check local model performance
2. Adjust latency weights
3. Use performance mode for critical tasks
4. Consider hardware upgrades

### Issue 4: Fallback Failures

**Symptoms**: Errors when primary model fails

**Solutions**:

1. Ensure multiple providers configured
2. Check API keys and connectivity
3. Review fallback logic in router
4. Add more model options

## Rollback Plan

If migration fails, rollback steps:

1. **Environment Variables**:

   ```bash
   USE_MODEL_ROUTER=false
   MODEL_ROUTING_MODE=local-only
   ```

2. **Code Changes**:

   ```python
   # Revert to direct client usage
   anthropic_client = AsyncAnthropic(api_key=key)
   ```

3. **Configuration**:
   - Backup new config files
   - Restore original initialization

## Validation Checklist

Before completing migration:

- [ ] All existing tests pass
- [ ] Model selection works for all task types
- [ ] Costs are within budget
- [ ] Performance meets requirements
- [ ] Fallback mechanisms work
- [ ] Monitoring and logging functional
- [ ] Documentation updated
- [ ] Team trained on new system

## Support

For migration issues:

1. Check logs: `LOG_LEVEL=DEBUG`
2. Review configuration files
3. Test with dry run mode
4. Monitor usage metrics
5. Consult troubleshooting section

## Next Steps

After successful migration:

1. Optimize model selection policies
2. Add more local models
3. Implement advanced monitoring
4. Train team on new capabilities
5. Plan cost optimization strategies
