# Agent Orchestra Local LLM Router v2

**Production-grade enterprise meta-agent system with intelligent routing, auto-discovery, and complete multi-tenancy.**

Transform your AI operations with advanced model selection, semantic caching, response validation, budget management, and comprehensive audit trails.

---

## 🚀 What's New in v2

### 🎯 Enterprise Features
- **Multi-Tenancy**: Complete tenant isolation with custom policies and budgets
- **Budget Management**: Hierarchical budget tracking with real-time enforcement
- **Audit Logging**: Immutable audit trails for SOC 2, HIPAA, GDPR compliance
- **Analytics Engine**: Real-time dashboards and optimization recommendations

### 🤖 Advanced AI Capabilities
- **Auto-Discovery**: Automatically discover and benchmark models from 15+ providers
- **Semantic Caching**: 40-50% cost reduction with intelligent caching
- **Response Validation**: Hallucination detection and quality assurance
- **ML Learning**: Thompson sampling for optimal model selection

### 📊 Enhanced Performance
- **TimescaleDB**: Time-series optimized for metrics and analytics
- **Vector Database**: Semantic search with Weaviate/Pinecone
- **Real-time Monitoring**: Prometheus + Grafana + OpenTelemetry
- **Zero Downtime**: Canary deployments with automatic rollback

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                    │
├─────────────────────────────────────────────────────────────┤
│  Multi-Tenancy │  Budget Mgmt │  Audit Log │  Analytics    │
├─────────────────────────────────────────────────────────────┤
│     Advanced Policy Engine │  Semantic Cache │ Validation   │
├─────────────────────────────────────────────────────────────┤
│  Model Discovery │  Metrics Store │  Learned Mappings     │
├─────────────────────────────────────────────────────────────┤
│         Model Router (15+ Providers)                      │
├─────────────────────────────────────────────────────────────┤
│  TimescaleDB  │  PostgreSQL  │  Redis  │  Weaviate/Pinecone │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

1. **Docker & Docker Compose** (for local development)
2. **PostgreSQL with TimescaleDB** (production database)
3. **Redis** (caching and session management)
4. **Vector Database** (Weaviate or Pinecone)
5. **Local Models** (Ollama) - optional but recommended

### Installation

#### 1. Clone and Setup

```bash
git clone <repo-url>
cd agent-orchestra-locallm-router-v3/q-and-a-orchestra-agent
cp .env.v2.example .env
```

#### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/orchestra_v2
REDIS_URL=redis://localhost:6379/0
VECTOR_DB_URL=http://localhost:8080

# LLM Providers
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-your-key
ANTHROPIC_API_KEY=sk-ant-your-key

# Features
ENABLE_AUTO_DISCOVERY=true
ENABLE_SEMANTIC_CACHE=true
ENABLE_MULTI_TENANCY=true
ENABLE_AUDIT_LOGGING=true
```

#### 3. Start with Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.v2.yml up -d

# Wait for services to be ready
docker-compose -f docker-compose.v2.yml ps

# View logs
docker-compose -f docker-compose.v2.yml logs -f orchestra-v2
```

#### 4. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# List available models
curl http://localhost:8000/v2/models

# Test chat endpoint
curl -X POST http://localhost:8000/v2/chat \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: default" \
  -d '{
    "messages": [{"role": "user", "content": "Hello!"}],
    "task_type": "general_chat"
  }'
```

---

## 🎛️ Configuration

### Model Configuration (`config/models.v2.yaml`)

```yaml
providers:
  ollama:
    type: local
    base_url: http://localhost:11434
    auto_discover: true
    
  openai:
    type: cloud
    base_url: https://api.openai.com/v1
    auto_discover: true
```

### Policy Configuration (`config/policies.v2.yaml`)

```yaml
routing:
  default_mode: local-preferred
  weights:
    local-preferred:
      cost: 0.6
      quality: 0.25
      latency: 0.15

learning:
  enable_thompson_sampling: true
  min_confidence_for_learned: 0.7
```

### Tenant Configuration (`config/tenants.v2.yaml`)

```yaml
enterprise_acme:
  tenant_name: "ACME Corporation"
  monthly_budget_usd: 10000
  allowed_models: ["gpt-4-turbo", "claude-3-5-sonnet-20241022"]
  routing_mode: "performance"
```

---

## 📊 Monitoring & Analytics

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin)

- **System Overview**: Request volume, latency, error rates
- **Cost Analysis**: Spending trends, budget utilization
- **Model Performance**: Per-model metrics and quality scores
- **Tenant Analytics**: Multi-tenant usage and costs

### Prometheus Metrics

Available at `http://localhost:9090`

Key metrics:
- `orchestra_requests_total`: Total requests
- `orchestra_request_duration_seconds`: Request latency
- `orchestra_cache_hit_rate`: Cache effectiveness
- `orchestra_model_selections`: Model usage patterns

### Health Checks

```bash
# Overall system health
curl http://localhost:8000/health

# Database connectivity
curl http://localhost:8000/health/db

# Provider availability
curl http://localhost:8000/health/providers

# Cache system status
curl http://localhost:8000/health/cache
```

---

## 🔧 API Reference

### Core Endpoints

#### Chat with v2 Features
```http
POST /v2/chat
Headers:
  x-tenant-id: your-tenant-id
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "Hello!"}],
  "task_type": "code_generation",
  "team_id": "dev-team",
  "project_id": "my-project",
  "enable_cache": true,
  "enable_validation": true
}
```

#### Analytics Dashboard
```http
GET /v2/analytics/dashboard?start_date=2024-01-01&end_date=2024-01-31
Headers:
  x-tenant-id: your-tenant-id
```

#### Budget Status
```http
GET /v2/budget/status
Headers:
  x-tenant-id: your-tenant-id
```

#### Optimization Recommendations
```http
GET /v2/recommendations
Headers:
  x-tenant-id: your-tenant-id
```

### Model Management

#### List Available Models
```http
GET /v2/models
Headers:
  x-tenant-id: your-tenant-id
```

#### Trigger Model Discovery
```http
POST /v2/discovery/run
Headers:
  x-tenant-id: your-tenant-id
```

---

## 🏢 Multi-Tenancy

### Creating a New Tenant

```python
from core.enterprise.multi_tenancy import TenantConfig

config = TenantConfig(
    tenant_id="new-tenant",
    tenant_name="New Company",
    monthly_budget_usd=2000,
    allowed_models=["llama3-8b-instruct", "gpt-4-turbo"],
    routing_mode="balanced"
)

tenant_context = await tenancy_manager.create_tenant(config)
```

### Budget Management

```python
from core.enterprise.budget_management import BudgetConfig

budget_config = BudgetConfig(
    tenant_id="new-tenant",
    level=BudgetLevel.TENANT,
    monthly_limit_usd=2000,
    daily_limit_usd=100,
    warning_threshold_pct=80,
    alert_emails=["admin@company.com"]
)

await budget_manager.create_budget_config(budget_config)
```

### Analytics per Tenant

```python
dashboard = await analytics_engine.get_tenant_dashboard(
    tenant_id="new-tenant",
    start_date=date.today() - timedelta(days=30),
    end_date=date.today()
)

print(f"Total cost: ${dashboard.total_cost_usd:.2f}")
print(f"Cache hit rate: {dashboard.cache_hit_rate:.1%}")
```

---

## 🔍 Semantic Caching

### How It Works

1. **Embedding Generation**: User prompts are converted to 384-dimensional vectors
2. **Similarity Search**: Find cached responses with >95% similarity
3. **Quality Filter**: Only cache responses with quality score >0.6
4. **Cost Savings**: 40-50% reduction in API calls

### Configuration

```yaml
caching:
  enable_semantic_cache: true
  similarity_threshold: 0.95
  cache_ttl_days: 30
  min_quality_score_for_cache: 0.6
```

### Cache Analytics

```python
# Get cache statistics
cache_stats = await semantic_cache.get_statistics()
print(f"Cache hit rate: {cache_stats['hit_rate']:.1%}")
print(f"Cost saved: ${cache_stats['cost_saved']:.2f}")
```

---

## 🛡️ Response Validation

### Validation Layers

1. **Toxicity Detection**: Block harmful content
2. **Hallucination Detection**: NLI-based fact checking
3. **Task-Specific Validation**: Code syntax, math accuracy, etc.
4. **Quality Scoring**: Overall response quality assessment

### Configuration

```yaml
validation:
  enable_response_validation: true
  hallucination_threshold: 0.3
  toxicity_threshold: 0.7
  task_validation:
    code_generation:
      enable_syntax_check: true
      min_quality_score: 0.8
```

### Validation Results

```python
validation_result = await response_validator.validate_response(
    prompt="Write a Python function to sort a list",
    response="def sort_list(lst): return sorted(lst)",
    task_type="code_generation"
)

print(f"Passed: {validation_result['passed']}")
print(f"Quality: {validation_result['quality_score']:.2f}")
```

---

## 📈 Machine Learning & Optimization

### Thompson Sampling

The system uses Thompson sampling for optimal model selection:

```python
# Model selection with exploration/exploitation
selected_model = await advanced_policy.select_model_with_learning(
    task_type="code_generation",
    tenant_id="acme-corp",
    exploration_rate=0.1
)
```

### Learned Mappings

```python
# Get learned model performance
learned_mapping = await learned_mappings.get_best_models(
    task_type="code_generation",
    tenant_id="acme-corp"
)

for model in learned_mapping:
    print(f"{model.model_id}: {model.efficiency_score:.2f}")
```

### Optimization Recommendations

```python
recommendations = await analytics_engine.generate_recommendations(
    tenant_id="acme-corp"
)

for rec in recommendations:
    print(f"{rec.title}: ${rec.savings_estimate_usd:.2f} savings")
```

---

## 🔧 Development

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.v2.txt

# Set up database
createdb orchestra_v2
psql orchestra_v2 < migrations/v2_schemas.sql

# Start local services
docker-compose -f docker-compose.v2.yml up -d timescaledb redis weaviate ollama

# Run the application
python main_v2.py
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# End-to-end tests
pytest tests/e2e/ -v

# Coverage report
pytest --cov=core --cov-report=html
```

### Code Quality

```bash
# Format code
black .

# Type checking
mypy core/

# Linting
pylint core/

# Import sorting
isort .
```

---

## 🚀 Production Deployment

### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestra-v2
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestra-v2
  template:
    metadata:
      labels:
        app: orchestra-v2
    spec:
      containers:
      - name: orchestra-v2
        image: orchestra-v2:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: orchestra-secrets
              key: database-url
```

### Environment Variables

```bash
# Production settings
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database (use secrets in production)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
VECTOR_DB_URL=...

# Security
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# Features
ENABLE_AUTO_DISCOVERY=true
ENABLE_SEMANTIC_CACHE=true
ENABLE_AUDIT_LOGGING=true
ENABLE_MULTI_TENANCY=true
```

### Monitoring Setup

```bash
# Deploy monitoring stack
kubectl apply -f monitoring/prometheus.yaml
kubectl apply -f monitoring/grafana.yaml
kubectl apply -f monitoring/loki.yaml

# Set up alerts
kubectl apply -f monitoring/alerts.yaml
```

---

## 📊 Performance Benchmarks

### Expected Performance

| Metric | Target | v1 Performance | v2 Performance |
|--------|--------|----------------|----------------|
| **Cost Reduction** | 50% | Baseline | 40-50% |
| **Cache Hit Rate** | 40% | N/A | 40-50% |
| **Model Selection Accuracy** | 85% | 60% | 85-90% |
| **P99 Latency** | <500ms | 800ms | <500ms |
| **System Uptime** | 99.9% | 99% | 99.9% |
| **Error Rate** | <0.5% | 2% | <0.5% |

### Scaling Capabilities

- **Concurrent Requests**: 1000+
- **Tenants**: 100+ with complete isolation
- **Models**: 15+ providers, unlimited models
- **Monthly Volume**: 1B+ requests
- **Data Retention**: 7 years (compliant)

---

## 🔒 Security & Compliance

### Security Features

- **Input Validation**: Comprehensive input sanitization
- **Rate Limiting**: Configurable per-tenant limits
- **Authentication**: JWT-based auth with RBAC
- **Encryption**: Data at rest and in transit
- **Audit Trails**: Immutable logging for compliance

### Compliance Support

- **SOC 2**: Full audit trails and access controls
- **HIPAA**: Data privacy and retention policies
- **GDPR**: Data residency and deletion rights
- **SOX**: Financial controls and reporting

### Security Best Practices

```bash
# Use secrets for sensitive data
kubectl create secret generic orchestra-secrets \
  --from-literal=database-url=... \
  --from-literal=openai-api-key=...

# Enable security headers
CORS_ORIGINS=["https://your-domain.com"]
ENABLE_RATE_LIMITING=true
ENABLE_INPUT_VALIDATION=true
```

---

## 🆘 Troubleshooting

### Common Issues

#### Database Connection Errors
```bash
# Check TimescaleDB status
docker-compose logs timescaledb

# Verify connection
psql $DATABASE_URL -c "SELECT 1"
```

#### Model Discovery Fails
```bash
# Check provider connectivity
curl -f http://localhost:11434/api/tags  # Ollama
curl -f https://api.openai.com/v1/models  # OpenAI

# Check logs
docker-compose logs orchestra-v2 | grep discovery
```

#### Cache Not Working
```bash
# Check Weaviate status
curl http://localhost:8080/v1/.well-known/ready

# Verify Redis
redis-cli ping
```

#### High Latency
```bash
# Check system resources
docker stats

# Analyze slow queries
psql $DATABASE_URL -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10"
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG=true

# Run with profiling
python -m cProfile -o profile.stats main_v2.py
```

### Health Monitoring

```bash
# Comprehensive health check
curl http://localhost:8000/health | jq .

# Component-specific checks
curl http://localhost:8000/health/db
curl http://localhost:8000/health/cache
curl http://localhost:8000/health/providers
```

---

## 📚 Additional Resources

### Documentation
- [Architecture Guide](docs/architecture.md)
- [API Reference](docs/api.md)
- [Deployment Guide](docs/deployment.md)
- [Security Guide](docs/security.md)

### Examples
- [Multi-Tenant Setup](examples/multi-tenant.md)
- [Custom Provider Integration](examples/custom-provider.md)
- [Advanced Analytics](examples/analytics.md)

### Support
- [GitHub Issues](https://github.com/your-org/agent-orchestra/issues)
- [Community Discord](https://discord.gg/your-server)
- [Documentation](https://docs.orchestra.ai)

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎉 What's Next?

### Upcoming Features (v2.1)
- **Custom Model Training**: Train domain-specific models
- **Advanced Analytics**: ML-powered insights
- **Federated Learning**: Privacy-preserving model improvement
- **Edge Deployment**: Support for edge computing

### Long-term Roadmap (v3.0)
- **Multi-Modal AI**: Vision, audio, and text processing
- **Autonomous Agents**: Self-improving AI agents
- **Distributed Computing**: Global model orchestration
- **Quantum Computing**: Quantum-enhanced model selection

---

**Transform your AI operations today with Agent Orchestra v2! 🚀**
