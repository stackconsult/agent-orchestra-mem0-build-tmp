# Context Engineering in Agent Orchestra

**StackConsulting Production Pattern #3:** 6-Layer Context Engineering wired into every deployment. No more "tell me about your system" loops. Agents know who you are, what you want, and the rules they operate under from the first message.

## Why Context Engineering?

Prompts are instructions. Context is reality. Without it, you're shipping intern-grade AI that hallucinates constraints and forgets your stack.

The 6 Layers Framework (adapted from Miqdad Jaffer @ OpenAI) is now baked into Agent Orchestra:

1. **User:** Who you are, your tenant, roles, preferences, memory history
2. **Intent:** What job you're hiring the system to do right now
3. **Domain:** Your repo, project entities, docs, relationships
4. **Rules:** Hard walls (compliance, permissions) + soft walls (tone, style)
5. **Environment:** Deployment context, model routing, feature flags
6. **Exposition:** Fused, prioritized, token-optimized payload for LLMs

This is your default context surface. Every `/v2/chat` request auto-builds the full envelope.

## How It Works

```
Raw Request → Context Builder → 6 Layers → Exposition Payload → Orchestrator → Agents
```

Entry point: `context_engineering.builder.build_context_envelope()`

- Pulls from auth claims, mem0, repo analyzer, config, env vars
- Outputs `ContextEnvelope` Pydantic model
- Orchestrator injects `exposition.narrative` as system context
- Agents use `exposition.structured` for deterministic branching

## The 6 Layers (Mapped to Your System)

### 1. User Layer
- **Source:** Auth middleware, mem0 memory system
- **What it captures:** ID, tenant, roles, expertise level, preferences, history summary
- **Example:** `"user_id: stackconsult-admin, expertise: expert, prefers: concise operator docs"`

### 2. Intent Layer
- **Source:** `task_type` + message analysis
- **What it captures:** Primary intent, success criteria, constraints, confidence
- **Drives:** Agent selection (analysis → Repo Analyzer first)
- **Example:** `"primary_intent: architecture_design, constraints: max_iterations=3"`

### 3. Domain Layer
- **Source:** Repository Analyzer agent, file tree, project metadata
- **What it captures:** Repo summary, components, related docs, entity relationships
- **Example:** `"repo_path: /your-project, key_components: {backend: FastAPI, db: Postgres}"`

### 4. Rules Layer (Two-Wall System)
**Hard Walls** (never break):
- No live code execution without approval
- PII redaction, secrets never logged
- Schema validation enforced

**Soft Walls** (StackConsulting DNA):
- Voice: sharp, practical, operator-focused
- Style: short paragraphs, bullets, no fluff
- Deliverables: actionable next steps always

### 5. Environment Layer
- **Source:** Env vars, deployment, feature flags
- **What it captures:** `ENV`, model routing, system load, active sessions
- **Example:** `"production, model_routing: local-preferred, system_load: 0.65"`

### 6. Exposition Layer
The final payload—human-readable narrative + machine-readable structured data.

Example (truncated):
```
User: ID: stackconsult-admin, Tenant: creditx-prod, Roles: [admin, engineer]
Intent: Primary: repo_analysis, Success: Deliver actionable insights + next steps
Domain: Repo: creditx-engine, Components: {api: FastAPI, db: Postgres+pgvector}
Rules: Hard: no_secrets_logging; Soft: concise_operator_voice
Environment: production, model_routing: local-preferred
```

## Integration Map

```
POST /v2/chat
├── Auth middleware → auth_claims
├── Context builder → ContextEnvelope
├── Model router → chooses Claude/local based on env.intent
├── Orchestrator → injects exposition into agent system prompt
└── Agents → use structured fields for branching
```

Key files:
- `context_engineering/builder.py` – the main factory
- `context_engineering/models.py` – all Pydantic schemas
- `sources/*.py` – pluggable layer builders
- `main_v2.py` – FastAPI integration
- `orchestrator/core.py` – consumption layer

## Customization Guide

### Override Layers
```json
{
  "message": "...",
  "context": {
    "override_user_preferences": {"detail_level": "expert"},
    "override_rules": {"hard_walls": {"allow_live_exec": true}}
  }
}
```

### Extend Sources
1. Add `context_engineering/sources/my_source.py`
2. Implement layer builder function
3. Register in `builder.build_context_envelope()`
4. Test with `./scripts/test_context_builder.py`

### Token Budget Control
- Config in `config/context_config.py`
- Default: 8k total (2k per major layer)
- Exposition auto-prunes based on priority

## Production Checklist

- [ ] Context builder unit tests pass (`pytest context_engineering/`)
- [ ] `/v2/chat?debug=context` shows full envelope
- [ ] Agents respect hard walls (no hallucinated code exec)
- [ ] Mem0 integration captures user history across sessions
- [ ] Repo analyzer runs <2s for 10k LOC projects
- [ ] Token budget enforcement prevents context overflow
- [ ] Context caching reduces redundant builds

## Extension Patterns

### Multi-Tenant
- Override `tenant_policies` in auth middleware
- Per-tenant rule sets and preferences
- Isolated domain contexts

### RAG-Heavy
- Extend `domain_graph.py` with Pinecone/Supabase vector search
- Cache RAG results in domain layer
- Semantic similarity for document selection

### Voice Agents
- Add `voice_context` source for transcription + speaker ID
- Adjust user preferences based on vocal patterns
- Real-time context updates during conversation

### Long-Running Tasks
- Add `session_state` to Environment layer
- Persist context across task steps
- Progress tracking in domain layer

## Debugging Context

Enable debug mode to see full context:
```bash
curl -X POST "http://localhost:8000/v2/chat?debug=context" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "Analyze my repo"}'
```

Response includes:
- Full `ContextEnvelope` in `debug.context`
- Token usage per layer
- Processing time breakdown
- Source attribution

## Performance Considerations

1. **Parallel Layer Building:** All 6 layers build concurrently
2. **Smart Caching:** Context cached per session + intent
3. **Incremental Updates:** Only rebuild changed layers
4. **Lazy Loading:** Heavy sources (repo analysis) on-demand
5. **Token Pruning:** Auto-truncate based on priority

## This is Your Competitive Moat

Most teams prompt-engineer. You context-engineer. Every deployment inherits production-grade context reasoning.

When you clone this template, the 6 layers auto-adapt to the domain. Zero prompt tuning required.

---

**Paste this into your IDE → "Implement from docs" → ship.**
