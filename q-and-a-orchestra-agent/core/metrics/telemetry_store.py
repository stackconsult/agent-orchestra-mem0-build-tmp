"""
Telemetry Store

Interfaces with TimescaleDB for storing and querying request metrics.
Provides optimized time-series data storage and retrieval.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection

from .request_telemetry import RequestMetrics


logger = logging.getLogger(__name__)


class TelemetryStore:
    """TimescaleDB interface for telemetry data storage."""
    
    def __init__(self, connection_string: str):
        """Initialize telemetry store."""
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            await self._create_tables()
            await self._create_indexes()
            await self._create_continuous_aggregates()
            
            logger.info("Telemetry store initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize telemetry store: {e}")
            raise
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Telemetry store connection closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        if not self.pool:
            raise RuntimeError("Telemetry store not initialized")
        
        async with self.pool.acquire() as conn:
            yield conn
    
    async def _create_tables(self):
        """Create TimescaleDB tables."""
        async with self.get_connection() as conn:
            # Create request_metrics hypertable
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS request_metrics (
                    time TIMESTAMPTZ NOT NULL,
                    request_id UUID NOT NULL,
                    tenant_id VARCHAR(255) NOT NULL,
                    user_id VARCHAR(255),
                    model_id VARCHAR(255) NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    
                    latency_ms FLOAT,
                    input_tokens INT,
                    output_tokens INT,
                    total_tokens INT,
                    cost_usd FLOAT,
                    
                    was_cached BOOLEAN,
                    cache_hit BOOLEAN,
                    response_valid BOOLEAN,
                    quality_score FLOAT,
                    
                    criticality VARCHAR(20),
                    success BOOLEAN,
                    error_message TEXT,
                    
                    ip_address VARCHAR(45),
                    user_agent TEXT
                );
            """)
            
            # Convert to hypertable if not already
            await conn.execute("""
                SELECT create_hypertable(
                    'request_metrics', 
                    'time',
                    if_not_exists => TRUE
                );
            """)
            
            # Create model_profiles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS model_profiles (
                    id SERIAL PRIMARY KEY,
                    provider VARCHAR(50) NOT NULL,
                    model_id VARCHAR(255) NOT NULL,
                    display_name VARCHAR(255),
                    
                    context_window INT,
                    estimated_cost_input_per_1k FLOAT,
                    estimated_cost_output_per_1k FLOAT,
                    
                    capabilities TEXT[],
                    quality_tier VARCHAR(20),
                    
                    benchmark_results JSONB,
                    discovered_at TIMESTAMP,
                    last_updated TIMESTAMP,
                    last_tested TIMESTAMP,
                    
                    UNIQUE (provider, model_id)
                );
            """)
            
            # Create learned_mappings table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_mappings (
                    id SERIAL PRIMARY KEY,
                    task_type VARCHAR(50) NOT NULL,
                    model_id VARCHAR(255) NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    
                    avg_latency_ms FLOAT,
                    p95_latency_ms FLOAT,
                    avg_quality_score FLOAT,
                    avg_cost_usd FLOAT,
                    success_rate FLOAT,
                    cache_hit_rate FLOAT,
                    
                    efficiency_score FLOAT,
                    rank_in_category INT,
                    
                    sample_count INT,
                    confidence FLOAT,
                    
                    last_trained TIMESTAMP,
                    
                    UNIQUE (task_type, model_id)
                );
            """)
            
            # Create cached_responses table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_responses (
                    cache_key VARCHAR(255) PRIMARY KEY,
                    original_prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    model_id VARCHAR(255) NOT NULL,
                    cost_saved FLOAT,
                    quality_score FLOAT,
                    cached_at TIMESTAMP,
                    hit_count INT DEFAULT 0,
                    last_hit TIMESTAMP,
                    expires_at TIMESTAMP
                );
            """)
    
    async def _create_indexes(self):
        """Create performance indexes."""
        async with self.get_connection() as conn:
            # Request metrics indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_metrics_tenant_time 
                ON request_metrics (tenant_id, time DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_metrics_model_time 
                ON request_metrics (model_id, time DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_metrics_task_time 
                ON request_metrics (task_type, time DESC);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_request_metrics_provider_time 
                ON request_metrics (provider, time DESC);
            """)
            
            # Cached responses indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_responses_task_type 
                ON cached_responses (task_type);
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cached_responses_expires_at 
                ON cached_responses (expires_at);
            """)
    
    async def _create_continuous_aggregates(self):
        """Create continuous aggregates for analytics."""
        async with self.get_connection() as conn:
            # Daily model stats
            await conn.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS model_daily_stats
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 day', time) AS day,
                    model_id,
                    provider,
                    COUNT(*) AS request_count,
                    AVG(latency_ms) AS avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                    AVG(quality_score) AS avg_quality,
                    AVG(cost_usd) AS avg_cost,
                    SUM(cost_usd) AS total_cost,
                    COUNTIF(success) / COUNT(*) AS success_rate,
                    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate
                FROM request_metrics
                GROUP BY day, model_id, provider;
            """)
            
            # Add refresh policy
            await conn.execute("""
                SELECT add_continuous_aggregate_policy(
                    'model_daily_stats',
                    start_offset => INTERVAL '1 day',
                    end_offset => INTERVAL '1 hour',
                    schedule_interval => INTERVAL '1 hour'
                );
            """)
            
            # Hourly tenant stats
            await conn.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS tenant_hourly_stats
                WITH (timescaledb.continuous) AS
                SELECT
                    time_bucket('1 hour', time) AS hour,
                    tenant_id,
                    COUNT(*) AS request_count,
                    AVG(latency_ms) AS avg_latency,
                    SUM(cost_usd) AS total_cost,
                    AVG(quality_score) AS avg_quality,
                    COUNTIF(success) / COUNT(*) AS success_rate
                FROM request_metrics
                GROUP BY hour, tenant_id;
            """)
            
            await conn.execute("""
                SELECT add_continuous_aggregate_policy(
                    'tenant_hourly_stats',
                    start_offset => INTERVAL '1 hour',
                    end_offset => INTERVAL '10 minutes',
                    schedule_interval => INTERVAL '10 minutes'
                );
            """)
    
    async def store_request_metrics(self, metrics: RequestMetrics):
        """Store request metrics in TimescaleDB."""
        try:
            record = metrics.to_timescale_record()
            
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO request_metrics (
                        time, request_id, tenant_id, user_id, model_id, provider, task_type,
                        latency_ms, input_tokens, output_tokens, total_tokens, cost_usd,
                        was_cached, cache_hit, response_valid, quality_score,
                        criticality, success, error_message, ip_address, user_agent
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7,
                        $8, $9, $10, $11, $12,
                        $13, $14, $15, $16,
                        $17, $18, $19, $20, $21
                    )
                """, 
                    record["time"], record["request_id"], record["tenant_id"], record["user_id"],
                    record["model_id"], record["provider"], record["task_type"],
                    record["latency_ms"], record["input_tokens"], record["output_tokens"],
                    record["total_tokens"], record["cost_usd"],
                    record["was_cached"], record["cache_hit"], record["response_valid"],
                    record["quality_score"],
                    record["criticality"], record["success"], record["error_message"],
                    record["ip_address"], record["user_agent"]
                )
                
        except Exception as e:
            logger.error(f"Failed to store request metrics: {e}")
            raise
    
    async def get_model_performance(self, 
                                 model_id: str,
                                 time_range: timedelta = timedelta(days=7)) -> Dict[str, Any]:
        """Get performance metrics for a specific model."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS request_count,
                    AVG(latency_ms) AS avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_latency,
                    AVG(quality_score) AS avg_quality,
                    AVG(cost_usd) AS avg_cost,
                    SUM(cost_usd) AS total_cost,
                    COUNTIF(success) / COUNT(*) AS success_rate,
                    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate
                FROM request_metrics
                WHERE model_id = $1 AND time >= $2
            """, model_id, start_time)
            
            return dict(row) if row else {}
    
    async def get_tenant_usage(self,
                             tenant_id: str,
                             time_range: timedelta = timedelta(days=30)) -> Dict[str, Any]:
        """Get usage statistics for a tenant."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS request_count,
                    COUNT(DISTINCT model_id) AS models_used,
                    COUNT(DISTINCT task_type) AS task_types_used,
                    SUM(cost_usd) AS total_cost,
                    AVG(latency_ms) AS avg_latency,
                    AVG(quality_score) AS avg_quality,
                    COUNTIF(success) / COUNT(*) AS success_rate,
                    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate
                FROM request_metrics
                WHERE tenant_id = $1 AND time >= $2
            """, tenant_id, start_time)
            
            return dict(row) if row else {}
    
    async def get_task_type_performance(self,
                                      task_type: str,
                                      time_range: timedelta = timedelta(days=7)) -> List[Dict[str, Any]]:
        """Get performance metrics by model for a specific task type."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            rows = await conn.fetch("""
                SELECT
                    model_id,
                    provider,
                    COUNT(*) AS request_count,
                    AVG(latency_ms) AS avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                    AVG(quality_score) AS avg_quality,
                    AVG(cost_usd) AS avg_cost,
                    COUNTIF(success) / COUNT(*) AS success_rate,
                    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate,
                    AVG(efficiency_score) AS avg_efficiency
                FROM request_metrics
                WHERE task_type = $1 AND time >= $2
                GROUP BY model_id, provider
                ORDER BY avg_efficiency DESC
            """, task_type, start_time)
            
            return [dict(row) for row in rows]
    
    async def get_cost_analysis(self,
                              time_range: timedelta = timedelta(days=30)) -> Dict[str, Any]:
        """Get cost analysis across all models and providers."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            # Overall cost stats
            overall = await conn.fetchrow("""
                SELECT
                    SUM(cost_usd) AS total_cost,
                    COUNT(*) AS total_requests,
                    AVG(cost_usd) AS avg_cost_per_request,
                    COUNT(DISTINCT tenant_id) AS active_tenants,
                    COUNT(DISTINCT model_id) AS models_used
                FROM request_metrics
                WHERE time >= $1
            """, start_time)
            
            # Cost by provider
            provider_costs = await conn.fetch("""
                SELECT
                    provider,
                    SUM(cost_usd) AS total_cost,
                    COUNT(*) AS request_count,
                    AVG(cost_usd) AS avg_cost_per_request
                FROM request_metrics
                WHERE time >= $1
                GROUP BY provider
                ORDER BY total_cost DESC
            """, start_time)
            
            # Cost by tenant (top 10)
            tenant_costs = await conn.fetch("""
                SELECT
                    tenant_id,
                    SUM(cost_usd) AS total_cost,
                    COUNT(*) AS request_count,
                    AVG(cost_usd) AS avg_cost_per_request
                FROM request_metrics
                WHERE time >= $1
                GROUP BY tenant_id
                ORDER BY total_cost DESC
                LIMIT 10
            """, start_time)
            
            return {
                "overall": dict(overall) if overall else {},
                "by_provider": [dict(row) for row in provider_costs],
                "by_tenant": [dict(row) for row in tenant_costs]
            }
    
    async def get_latency_trends(self,
                               model_id: Optional[str] = None,
                               time_range: timedelta = timedelta(days=7)) -> List[Dict[str, Any]]:
        """Get latency trends over time."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            if model_id:
                query = """
                    SELECT
                        time_bucket('1 hour', time) AS hour,
                        AVG(latency_ms) AS avg_latency,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                        COUNT(*) AS request_count
                    FROM request_metrics
                    WHERE model_id = $1 AND time >= $2
                    GROUP BY hour
                    ORDER BY hour
                """
                params = [model_id, start_time]
            else:
                query = """
                    SELECT
                        time_bucket('1 hour', time) AS hour,
                        AVG(latency_ms) AS avg_latency,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
                        COUNT(*) AS request_count
                    FROM request_metrics
                    WHERE time >= $1
                    GROUP BY hour
                    ORDER BY hour
                """
                params = [start_time]
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_quality_trends(self,
                               task_type: Optional[str] = None,
                               time_range: timedelta = timedelta(days=7)) -> List[Dict[str, Any]]:
        """Get quality score trends over time."""
        start_time = datetime.now() - time_range
        
        async with self.get_connection() as conn:
            if task_type:
                query = """
                    SELECT
                        time_bucket('1 hour', time) AS hour,
                        AVG(quality_score) AS avg_quality,
                        COUNT(*) AS request_count,
                        COUNTIF(response_valid) / COUNT(*) AS validation_rate
                    FROM request_metrics
                    WHERE task_type = $1 AND time >= $2
                    GROUP BY hour
                    ORDER BY hour
                """
                params = [task_type, start_time]
            else:
                query = """
                    SELECT
                        time_bucket('1 hour', time) AS hour,
                        AVG(quality_score) AS avg_quality,
                        COUNT(*) AS request_count,
                        COUNTIF(response_valid) / COUNT(*) AS validation_rate
                    FROM request_metrics
                    WHERE time >= $1
                    GROUP BY hour
                    ORDER BY hour
                """
                params = [start_time]
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def cleanup_old_data(self, retention_days: int = 90):
        """Clean up old data beyond retention period."""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        async with self.get_connection() as conn:
            # Delete old request metrics
            result = await conn.execute("""
                DELETE FROM request_metrics
                WHERE time < $1
            """, cutoff_date)
            
            # Delete expired cached responses
            await conn.execute("""
                DELETE FROM cached_responses
                WHERE expires_at < NOW()
            """)
            
            logger.info(f"Cleaned up data older than {cutoff_date}")
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics and health information."""
        async with self.get_connection() as conn:
            # Table sizes
            table_sizes = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)
            
            # Request metrics count
            total_requests = await conn.fetchval("""
                SELECT COUNT(*) FROM request_metrics
            """)
            
            # Date range of data
            date_range = await conn.fetchrow("""
                SELECT 
                    MIN(time) as earliest_record,
                    MAX(time) as latest_record
                FROM request_metrics
            """)
            
            return {
                "table_sizes": [dict(row) for row in table_sizes],
                "total_requests": total_requests,
                "date_range": dict(date_range) if date_range else {}
            }
