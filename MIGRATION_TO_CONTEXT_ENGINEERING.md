# Migration Guide: Adding Context Engineering to Agent Orchestra

This guide helps you migrate your existing Agent Orchestra v2 installation to include the 6-Layer Context Engineering system.

## Overview

Context Engineering transforms your AI system from prompt-dependent to context-aware. Agents will automatically understand user identity, intent, domain context, rules, and environment without explicit prompting.

## What Changes

### Before (Without Context Engineering)

```python
# Agents receive minimal context
response = await model_router.select_and_invoke(
    task=TaskProfile(task_type="analysis"),
    messages=[{"role": "user", "content": "Analyze my repo"}]
)
```

### After (With Context Engineering)

```python
# Full 6-layer context built automatically
context_envelope = await build_context_envelope(
    auth_claims=auth_data,
    request_body=request_data,
    mem0_client=mem0_client,
    repo_analyzer_client=repo_analyzer
)

response = await context_aware_router.select_and_invoke_with_context(
    task=task,
    messages=messages,
    context_envelope=context_envelope
)
```

## Migration Steps

### Step 1: Update Dependencies

Add context engineering dependencies:

```bash
# Add to requirements.txt
pip install mem0ai langchain sentence-transformers tiktoken
pip install gitpython tree-sitter chromadb aiocache
```

Or use the provided requirements file:

```bash
pip install -r requirements.context.txt
```

### Step 2: Add Context Engineering Module

Copy the context engineering module to your project:

```bash
cp -r context_engineering/ /path/to/your/q-and-a-orchestra-agent/
```

### Step 3: Update Environment Variables

Add these to your `.env` file:

```env
# Context Engineering
CONTEXT_ENGINEERING_ENABLED=true
MAX_CONTEXT_TOKENS=8000
CONTEXT_CACHE_ENABLED=true
CONTEXT_DEBUG=false

# Memory System (Mem0)
MEM0_API_KEY=your-mem0-api-key

# Context Sources
CONTEXT_BUILD_TIMEOUT=15000
CONTEXT_CACHE_TTL=300
```

### Step 4: Update Main Application

Replace your `main_v2.py` chat endpoint with the context-aware version:

```python
# Import context engineering
from context_engineering import build_context_envelope, ContextConfig

# Update the chat endpoint
@app.post("/v2/chat")
async def chat_v2_with_context(
    request: ChatRequest,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context),
    auth_claims: Dict[str, Any] = Depends(get_auth_claims)
):
    # Build context envelope
    context_envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body=request.dict(),
        mem0_client=mem0_client,
        repo_analyzer_client=repo_analyzer_client,
        tenant_policies=tenant_context.policies
    )
    
    # Use context-aware router
    result = await context_aware_router.select_and_invoke_with_context(
        task=task,
        messages=messages,
        context_envelope=context_envelope
    )
    
    return result
```

### Step 5: Update Model Router

Replace the standard model router with the context-aware version:

```python
# In your lifespan function
model_router = ContextAwareModelRouter(dry_run=dry_run)
```

### Step 6: Update Orchestrator

Use the context-aware orchestrator:

```python
from orchestrator.context_aware_orchestrator import ContextAwareOrchestrator

# In your lifespan function
orchestrator = ContextAwareOrchestrator(anthropic_client, redis_url)
```

### Step 7: Add Context Sources

Configure your context sources:

```python
# Mem0 client for user history
if os.getenv("MEM0_API_KEY"):
    from services.mem0_client import Mem0Client
    mem0_client = Mem0Client(api_key=os.getenv("MEM0_API_KEY"))

# Repository analyzer is already part of orchestrator
repo_analyzer_client = orchestrator.repository_analyzer
```

## Configuration Options

### Context Budget

Control token usage per layer:

```python
context_config = ContextConfig(
    max_total_tokens=6000,  # Total budget
    layers={
        "user": ContextLayerConfig(max_tokens=1500),
        "intent": ContextLayerConfig(max_tokens=500),
        "domain": ContextLayerConfig(max_tokens=2000),
        "rules": ContextLayerConfig(max_tokens=1000),
        "environment": ContextLayerConfig(max_tokens=500),
        "exposition": ContextLayerConfig(max_tokens=500),
    }
)
```

### Source Priorities

Adjust which sources take precedence:

```python
source_config = {
    "auth_claims": ContextSourceConfig(priority=100),
    "mem0": ContextSourceConfig(priority=90),
    "repo_analyzer": ContextSourceConfig(priority=80),
    "config": ContextSourceConfig(priority=70),
}
```

### Feature Flags

Enable/disable features:

```env
FEATURE_CONTEXT_ENGINEERING_V2=true
FEATURE_SEMANTIC_CACHE=true
FEATURE_AUDIT_LOGGING=true
```

## Testing the Migration

### 1. Run Context Tests

```bash
python scripts/test_context_engineering.py
```

### 2. Debug Context Building

```bash
curl "http://localhost:8000/v2/context/debug?message=test&task_type=analysis"
```

### 3. Check Health Endpoint

```bash
curl http://localhost:8000/health
```

Look for `"context_engineering": "healthy"`.

## API Changes

### Request Format

New fields added to `/v2/chat`:

```json
{
  "messages": [...],
  "task_type": "repo_analysis",
  "repository_path": "/path/to/repo",
  "context_overrides": {
    "override_user_preferences": {"detail_level": "expert"}
  }
}
```

### Response Format

New fields in response:

```json
{
  "response": "...",
  "context_id": "ctx_123456",
  "context_token_count": 3456,
  "context_processing_time_ms": 45.2,
  "routing_metadata": {
    "routing_factors": {
      "intent": "repo_analysis",
      "expertise": "intermediate"
    }
  }
}
```

## Troubleshooting

### Context Building Fails

**Error**: `Failed to build domain context`

**Solution**: Check repository path and permissions:

```python
# Ensure repo path exists and is accessible
if not os.path.exists(repo_path):
    logger.warning(f"Repository not found: {repo_path}")
    # Continue without domain context
```

### High Token Usage

**Problem**: Context exceeds token budget

**Solution**: Adjust layer budgets or enable pruning:

```python
# Apply token budget
context_envelope = apply_token_budget(context_envelope, max_tokens=4000)
```

### Slow Performance

**Problem**: Context building is slow

**Solution**: Enable caching and adjust timeouts:

```env
CONTEXT_CACHE_ENABLED=true
CONTEXT_BUILD_TIMEOUT=10000
```

### Missing User History

**Problem**: User layer is empty

**Solution**: Configure Mem0 client:

```python
# Check Mem0 configuration
if not mem0_client:
    logger.warning("Mem0 client not configured")
```

## Best Practices After Migration

1. **Monitor Token Usage**: Keep an eye on context token consumption
2. **Cache Strategically**: Enable semantic caching for repeated queries
3. **Use Context Overrides**: For temporary preference changes
4. **Validate Compliance**: Check that hard walls are enforced
5. **Debug Regularly**: Use the debug endpoint to inspect context

## Rollback Plan

If you need to rollback:

1. Restore original `main_v2.py`
2. Use standard `ModelRouter` instead of `ContextAwareModelRouter`
3. Remove context engineering dependencies
4. Update API documentation to reflect changes

## Performance Impact

Expected changes after migration:

- **Latency**: +20-50ms for context building
- **Token Usage**: +1000-4000 tokens per request
- **Memory**: +10-50MB for context caching
- **Accuracy**: Significant improvement in response relevance

## Support

For issues during migration:

1. Check logs: Context building errors are clearly logged
2. Use debug endpoint: `/v2/context/debug` shows full context
3. Run tests: `python scripts/test_context_engineering.py`
4. Check health: Context engineering status in `/health`

---

**Remember**: Context engineering is a gradual enhancement. Start with basic features, then enable advanced capabilities as you become comfortable with the system.
