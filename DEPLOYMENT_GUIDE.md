# Deployment Guide

## Overview

This guide covers deploying Agent Orchestra in various environments, from development to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Development Deployment](#development-deployment)
4. [Docker Deployment](#docker-deployment)
5. [Kubernetes Deployment](#kubernetes-deployment)
6. [Production Configuration](#production-configuration)
7. [Monitoring & Logging](#monitoring--logging)
8. [Security Considerations](#security-considerations)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Infrastructure Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4GB | 8GB+ |
| Storage | 20GB | 100GB+ SSD |
| Network | 100Mbps | 1Gbps |

### External Dependencies

- **PostgreSQL 13+** (for audit logs and analytics)
- **Redis 6+** (for caching and message bus)
- **Ollama** (optional, for local models)
- **Load Balancer** (production only)

---

## Environment Setup

### 1. Clone Repository

```bash
git clone https://github.com/stackconsult/agent-orchestra-production-build-tmp
cd agent-orchestra-production-build-tmp
```

### 2. Environment Variables

Create `.env` file based on your environment:

```bash
# Core Settings
ENV=production
DEBUG=false
SECRET_KEY=<generated-secret-key>
JWT_SECRET_KEY=<generated-jwt-secret>
API_HOST=0.0.0.0
API_PORT=8000

# Database Configuration
DATABASE_URL=postgresql://username:password@db-host:5432/orchestra
REDIS_URL=redis://redis-host:6379/0

# Model Configuration
MODEL_ROUTING_MODE=local-preferred
OLLAMA_BASE_URL=http://ollama:11434

# Cloud API Keys (Optional)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# CORS Configuration
APP_URL=https://api.yourdomain.com
FRONTEND_URL=https://yourdomain.com

# Security
ALLOWED_HOSTS=api.yourdomain.com,localhost
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Monitoring
SENTRY_DSN=https://...@sentry.io/...
LOG_LEVEL=INFO

# Budget & Limits
DEFAULT_MONTHLY_BUDGET=1000.0
DEFAULT_DAILY_BUDGET=100.0
MAX_REQUEST_SIZE=10485760  # 10MB
```

### 3. Generate Secrets

```bash
# Generate secret keys
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

---

## Development Deployment

### Local Development

```bash
# Setup Python environment
python -m venv venv
source venv/bin/activate

# Install dependencies
cd q-and-a-orchestra-agent
pip install -r requirements.txt

# Setup database
createdb orchestra
alembic upgrade head

# Start Redis
redis-server

# Start application
python main_v2.py
```

### Using Docker Compose (Development)

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./q-and-a-orchestra-agent:/app
    environment:
      - ENV=development
      - DEBUG=true
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      POSTGRES_DB: orchestra
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

```bash
docker-compose -f docker-compose.dev.yml up
```

---

## Docker Deployment

### Build Image

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY q-and-a-orchestra-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY q-and-a-orchestra-agent/ .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "main_v2:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t agent-orchestra:latest .

# Run
docker run -d \
  --name orchestra \
  -p 8000:8000 \
  --env-file .env \
  agent-orchestra:latest
```

### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    image: agent-orchestra:latest
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - ENV=production
    env_file:
      - .env
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:13
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups

  redis:
    image: redis:6-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app

volumes:
  postgres_data:
  redis_data:
```

---

## Kubernetes Deployment

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: orchestra
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orchestra-config
  namespace: orchestra
data:
  ENV: "production"
  DEBUG: "false"
  API_HOST: "0.0.0.0"
  API_PORT: "8000"
  MODEL_ROUTING_MODE: "local-preferred"
```

### Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: orchestra-secrets
  namespace: orchestra
type: Opaque
data:
  SECRET_KEY: <base64-encoded>
  JWT_SECRET_KEY: <base64-encoded>
  DATABASE_URL: <base64-encoded>
  REDIS_URL: <base64-encoded>
  ANTHROPIC_API_KEY: <base64-encoded>
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orchestra
  namespace: orchestra
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orchestra
  template:
    metadata:
      labels:
        app: orchestra
    spec:
      containers:
      - name: orchestra
        image: agent-orchestra:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: orchestra-config
        - secretRef:
            name: orchestra-secrets
        resources:
          requests:
            cpu: 200m
            memory: 512Mi
          limits:
            cpu: 500m
            memory: 1Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: orchestra-service
  namespace: orchestra
spec:
  selector:
    app: orchestra
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: orchestra-ingress
  namespace: orchestra
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: orchestra-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: orchestra-service
            port:
              number: 80
```

### Deploy

```bash
# Apply all configurations
kubectl apply -f k8s/

# Check deployment
kubectl get pods -n orchestra

# Check logs
kubectl logs -f deployment/orchestra -n orchestra
```

---

## Production Configuration

### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream orchestra {
        server app:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        listen 80;
        server_name api.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

        # API routes
        location / {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://orchestra;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Health check (no rate limit)
        location /health {
            proxy_pass http://orchestra;
            access_log off;
        }
    }
}
```

### Database Setup

```bash
# Create database
createdb orchestra

# Run migrations
cd q-and-a-orchestra-agent
alembic upgrade head

# Create indexes
psql -d orchestra -c "
CREATE INDEX CONCURRENTLY idx_audit_logs_timestamp 
ON audit_logs(timestamp);
CREATE INDEX CONCURRENTLY idx_tenant_id 
ON tenants(tenant_id);
"
```

---

## Monitoring & Logging

### Prometheus Metrics

```yaml
# k8s/monitoring.yaml
apiVersion: v1
kind: ServiceMonitor
metadata:
  name: orchestra-metrics
  namespace: orchestra
spec:
  selector:
    matchLabels:
      app: orchestra
  endpoints:
  - port: metrics
    path: /metrics
```

### Loki Logging

```yaml
# k8s/logging.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*orchestra*.log
      tag kubernetes.*
      format json
    </source>
    
    <match kubernetes.**>
      @type loki
      url http://loki:3100/loki/api/v1/push
      labels 
        job=orchestra
        namespace=orchestra
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Agent Orchestra Metrics",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

---

## Security Considerations

### Network Security

1. **Firewall Rules**
   ```bash
   # Allow only necessary ports
   ufw allow 22/tcp    # SSH
   ufw allow 80/tcp    # HTTP
   ufw allow 443/tcp   # HTTPS
   ufw enable
   ```

2. **Private Networks**
   - Database in private subnet
   - Redis in private subnet
   - Application in private subnet with load balancer

### Secrets Management

```bash
# Using Kubernetes Secrets
kubectl create secret generic orchestra-secrets \
  --from-literal=SECRET_KEY=$(openssl rand -base64 32) \
  --from-literal=JWT_SECRET_KEY=$(openssl rand -base64 32)

# Using AWS Secrets Manager
aws secretsmanager create-secret \
  --name orchestra/production \
  --secret-string file://secrets.json
```

### SSL/TLS

```bash
# Generate CSR
openssl req -new -newkey rsa:2048 -nodes -keyout key.pem -out csr.pem

# Get certificate from Let's Encrypt
certbot certonly --standalone -d api.yourdomain.com
```

---

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check connection
psql $DATABASE_URL -c "SELECT 1"

# Check logs
kubectl logs deployment/orchestra -n orchestra | grep -i database
```

#### 2. High Memory Usage

```bash
# Check memory usage
kubectl top pods -n orchestra

# Adjust limits
kubectl patch deployment orchestra -p '{"spec":{"template":{"spec":{"containers":[{"name":"orchestra","resources":{"limits":{"memory":"2Gi"}}}]}}}}'
```

#### 3. Rate Limiting

```bash
# Check rate limit status
curl -I http://localhost:8000/v2/chat

# Adjust limits
# Edit environment variable RATE_LIMIT_REQUESTS_PER_MINUTE
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Dependencies health
curl http://localhost:8000/health | jq '.components'
```

### Performance Tuning

1. **Database**
   ```sql
   -- Check slow queries
   SELECT query, mean_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_time DESC 
   LIMIT 10;
   ```

2. **Redis**
   ```bash
   # Check memory usage
   redis-cli info memory
   
   # Monitor slow operations
   redis-cli monitor
   ```

3. **Application**
   ```bash
   # Profile requests
   curl -X POST http://localhost:8000/v2/chat \
     -H "X-Debug: true" \
     -d '{"message": "test"}'
   ```

---

## Backup & Recovery

### Database Backup

```bash
# Automated backup
kubectl create cronjob db-backup \
  --schedule="0 2 * * *" \
  --image=postgres:13 \
  --env="PGPASSWORD=$DB_PASSWORD" \
  -- "pg_dump -h $DB_HOST -U $DB_USER orchestra | gzip > /backup/$(date +%Y%m%d).sql.gz"
```

### Disaster Recovery

```bash
# Restore database
gunzip -c backup.sql.gz | psql $DATABASE_URL

# Scale up application
kubectl scale deployment orchestra --replicas=5 -n orchestra
```

---

## Support

For deployment issues:
- Documentation: https://docs.agent-orchestra.com
- Issues: https://github.com/stackconsult/agent-orchestra/issues
- Email: support@agent-orchestra.com
- Slack: #agent-orchestra on community.slack.com
