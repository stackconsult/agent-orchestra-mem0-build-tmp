# Agent Orchestra Production Build

**Enterprise-grade multi-agent orchestration system with intelligent LLM routing and comprehensive security.**

A production-ready system that orchestrates specialized AI agents for software development tasks, featuring intelligent model routing, multi-tenancy, budget management, and enterprise-grade security controls.

---

## 🎯 What It Does

Agent Orchestra is a comprehensive AI-powered development assistant that:

- **Analyzes repositories** to understand codebase structure and architecture
- **Extracts requirements** from project specifications and user stories
- **Designs architectures** tailored to specific project needs
- **Creates implementation plans** with detailed step-by-step guidance
- **Validates implementations** against best practices and requirements
- **Routes intelligently** between local and cloud LLMs based on task complexity and cost

### 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (FastAPI)                    │
├─────────────────────────────────────────────────────────────┤
│  Security │ Rate Limit │ CORS │ Audit │ Multi-tenancy       │
├─────────────────────────────────────────────────────────────┤
│                   Model Router (Core)                       │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │   Local     │   Cloud     │   Hybrid    │   Fallback  │  │
│  │   Models    │   Models    │   Routing   │   Mechanism │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    Agent Orchestrator                       │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Repository  │ Requirements│ Architecture│ Implementation│ │
│  │ Analyzer    │ Extractor   │ Designer    │ Planner      │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│              Enterprise Features (v2)                       │
│  • Semantic Caching  • Analytics  • Budget Mgmt  • Audit    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (3.13 compatible)
- **Ollama** (for local models) - Optional but recommended
- **Redis** (for caching and message bus)
- **PostgreSQL** (for audit logs and analytics)

### Installation

```bash
# Clone the repository
git clone https://github.com/stackconsult/agent-orchestra-production-build-tmp
cd agent-orchestra-production-build-tmp

# Setup Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd q-and-a-orchestra-agent
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration
```

### Environment Configuration

Create `.env` file:

```bash
# Core Configuration
ENV=development
DEBUG=true
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/orchestra
REDIS_URL=redis://localhost:6379/0

# Local Models (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
MODEL_ROUTING_MODE=local-preferred

# Cloud API Keys (Optional - for fallback)
ANTHROPIC_API_KEY=your-anthropic-key
OPENAI_API_KEY=your-openai-key

# CORS Configuration
APP_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
```

### Running the System

```bash
# Start the main application
cd q-and-a-orchestra-agent
python main_v2.py

# Or use the development script
./scripts/start_dev.sh
```

The API will be available at `http://localhost:8000`

---

## 📚 API Documentation

### Core Endpoints

#### Chat with the Orchestra

```http
POST /v2/chat
Content-Type: application/json
Authorization: Bearer <token>

{
  "message": "Analyze my React project and suggest improvements",
  "session_id": "optional-session-id",
  "context": {
    "repository_path": "/path/to/repo",
    "task_type": "analysis"
  }
}
```

#### List Available Models

```http
GET /v2/models
Authorization: Bearer <token>
```

#### Health Check

```http
GET /health
```

#### Analytics Dashboard

```http
GET /v2/analytics/dashboard?start_date=2024-01-01&end_date=2024-01-31
Authorization: Bearer <token>
```

### Agent-Specific Operations

The system orchestrates multiple specialized agents:

1. **Repository Analyzer** - Analyzes codebase structure
2. **Requirements Extractor** - Extracts and clarifies requirements
3. **Architecture Designer** - Creates system architectures
4. **Implementation Planner** - Generates detailed implementation plans
5. **Validator** - Validates against best practices

---

## 🔒 Enterprise Security

This system implements comprehensive security controls with **A+ security rating**:

### Security Features

- **CORS Protection**: Environment-based origin configuration
- **Input Validation**: Comprehensive Pydantic schemas with XSS prevention
- **Rate Limiting**: Endpoint-specific limits (10/min for invoke, 5/min for auth)
- **Prompt Injection Detection**: Advanced pattern-based threat detection
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- **Audit Logging**: SOC 2, HIPAA, GDPR compliant logging
- **Multi-tenancy**: Tenant isolation with context management
- **Budget Management**: Cost controls and spending limits

### Security Verification

```bash
# Run comprehensive security checks
cd q-and-a-orchestra-agent
./scripts/security_verification.sh

# Expected: All checks PASSED ✅
```

---

## 🏢 Enterprise Features (v2)

### Multi-Tenancy

- Tenant isolation at all levels
- Per-tenant configurations and quotas
- Tenant-specific analytics and reporting

### Budget Management

- Cost tracking per tenant/model
- Configurable budget limits
- Automatic spending alerts
- Cost optimization recommendations

### Advanced Analytics

- Real-time usage metrics
- Model performance analytics
- Cost analysis and trends
- Custom dashboards

### Semantic Caching

- Intelligent response caching
- Semantic similarity matching
- Reduced API costs and latency
- Cache invalidation strategies

### Model Discovery

- Automatic model discovery
- Capability assessment
- Performance benchmarking
- Dynamic model registration

---

## 🛠️ Development

### Project Structure

```text
q-and-a-orchestra-agent/
├── agents/              # Specialized AI agents
├── core/                # Core routing and orchestration
├── providers/           # LLM provider clients
├── middleware/          # Security and utility middleware
├── schemas/             # Pydantic schemas
├── orchestrator/        # Message orchestration
├── integrations/        # External integrations
├── enterprise/          # Enterprise features
├── config/              # Configuration modules
└── scripts/             # Utility scripts
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run security tests
pytest tests/test_security.py -v

# Run with coverage
pytest --cov=. tests/
```

### Code Quality

```bash
# Lint code
flake8 .

# Format code
black .

# Type checking
mypy .

# Security scan
safety scan
bandit -r .
```

---

## 📊 Monitoring & Observability

### Health Checks

```bash
curl http://localhost:8000/health
```

### Metrics

- Request latency and throughput
- Model usage statistics
- Error rates and types
- Cost tracking
- Cache hit rates

### Logging

- Structured JSON logging
- Configurable log levels
- Audit trail for all actions
- Performance tracing

---

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t agent-orchestra .

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## ☸️ Kubernetes Deployment

```bash
# Apply configurations
kubectl apply -f deployment/kubernetes/

# Check status
kubectl get pods -n orchestra

# Port forward
kubectl port-forward svc/orchestra-api 8000:80
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: See the `/docs` directory
- **Issues**: Create an issue on GitHub
- **Security**: Report security issues to <security@example.com>

---

## 🎯 Roadmap

- [ ] Additional model providers (Cohere, Hugging Face)
- [ ] Advanced agent customization
- [ ] Real-time collaboration features
- [ ] Advanced analytics dashboard
- [ ] Plugin system for custom agents
- [ ] GraphQL API support
- [ ] WebSocket real-time updates

---

## Acknowledgments

Built with ❤️ for the developer community
