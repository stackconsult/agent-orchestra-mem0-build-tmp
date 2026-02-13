#!/bin/bash
# Development startup script with secure secrets generation
set -e

echo "=== Agent Orchestra Development Startup ==="

# Generate random passwords if not provided
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-$(openssl rand -base64 32)}
export REDIS_PASSWORD=${REDIS_PASSWORD:-$(openssl rand -base64 32)}
export TSDB_PASSWORD=${TSDB_PASSWORD:-$(openssl rand -base64 32)}
export JWT_SECRET=${JWT_SECRET:-$(openssl rand -base64 64)}
export SECRET_KEY=${SECRET_KEY:-$(openssl rand -base64 32)}
export GRAFANA_PASSWORD=${GRAFANA_PASSWORD:-$(openssl rand -base64 16)}

# Display passwords (only in development)
if [ "$ENV" = "development" ] || [ -z "$ENV" ]; then
    echo "=== Generated Secrets (Development Only) ==="
    echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
    echo "REDIS_PASSWORD=$REDIS_PASSWORD"
    echo "TSDB_PASSWORD=$TSDB_PASSWORD"
    echo "JWT_SECRET=$JWT_SECRET"
    echo "SECRET_KEY=$SECRET_KEY"
    echo "GRAFANA_PASSWORD=$GRAFANA_PASSWORD"
    echo "=========================================="
    echo ""
    echo "⚠️  WARNING: These secrets are displayed for development convenience only!"
    echo "   Never use these in production. Always use proper secrets management."
    echo ""
fi

# Check for required environment variables
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "❌ ERROR: POSTGRES_PASSWORD must be set"
    exit 1
fi

if [ -z "$REDIS_PASSWORD" ]; then
    echo "❌ ERROR: REDIS_PASSWORD must be set"
    exit 1
fi

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
docker-compose ps

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Access URLs:"
echo "   - API: http://localhost:8000"
echo "   - Grafana: http://localhost:3000 (admin: $GRAFANA_PASSWORD)"
echo "   - Prometheus: http://localhost:9091"
echo ""
echo "🔧 To stop services: docker-compose down"
echo "📝 To view logs: docker-compose logs -f"
