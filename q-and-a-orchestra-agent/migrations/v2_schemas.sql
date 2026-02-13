-- Agent Orchestra v2 Database Schemas
-- TimescaleDB + PostgreSQL for enterprise features

-- =============================================================================
-- TIMESCALEDB SCHEMAS (Time-Series Data)
-- =============================================================================

-- Create TimescaleDB extension if not exists
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Request Metrics Hypertable
CREATE TABLE IF NOT EXISTS request_metrics (
    time TIMESTAMPTZ NOT NULL,
    request_id UUID NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    team_id VARCHAR(255),
    project_id VARCHAR(255),
    
    -- Model information
    model_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    
    -- Performance metrics
    latency_ms FLOAT,
    input_tokens INT,
    output_tokens INT,
    total_tokens INT,
    cost_usd FLOAT,
    
    -- Cache metrics
    was_cached BOOLEAN DEFAULT false,
    cache_hit BOOLEAN DEFAULT false,
    cache_key VARCHAR(255),
    
    -- Quality metrics
    response_valid BOOLEAN,
    quality_score FLOAT,
    validation_reason TEXT,
    
    -- Request metadata
    criticality VARCHAR(20) DEFAULT 'normal',
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    error_type VARCHAR(50),
    
    -- Network information
    ip_address VARCHAR(45),
    user_agent TEXT,
    endpoint VARCHAR(255),
    
    -- Budget information
    budget_check_result VARCHAR(20),
    budget_warnings TEXT[],
    budget_actions TEXT[],
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT request_metrics_pkey PRIMARY KEY (request_id, time)
);

-- Convert to hypertable (partition by time)
SELECT create_hypertable('request_metrics', 'time', chunk_time_interval => INTERVAL '1 day');

-- Create indexes for efficient querying
CREATE INDEX idx_request_metrics_tenant_time ON request_metrics (tenant_id, time DESC);
CREATE INDEX idx_request_metrics_model_time ON request_metrics (model_id, time DESC);
CREATE INDEX idx_request_metrics_task_time ON request_metrics (task_type, time DESC);
CREATE INDEX idx_request_metrics_provider_time ON request_metrics (provider, time DESC);
CREATE INDEX idx_request_metrics_user_time ON request_metrics (user_id, time DESC) WHERE user_id IS NOT NULL;
CREATE INDEX idx_request_metrics_team_time ON request_metrics (team_id, time DESC) WHERE team_id IS NOT NULL;
CREATE INDEX idx_request_metrics_success ON request_metrics (success, time DESC) WHERE success = false;

-- Continuous aggregates for analytics
-- Daily model stats
CREATE MATERIALIZED VIEW model_daily_stats AS
SELECT 
    time_bucket('1 day', time) AS day,
    tenant_id,
    model_id,
    provider,
    task_type,
    COUNT(*) AS request_count,
    AVG(latency_ms) AS avg_latency,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_latency,
    AVG(quality_score) AS avg_quality,
    AVG(cost_usd) AS avg_cost,
    SUM(cost_usd) AS total_cost,
    COUNTIF(success) / COUNT(*) AS success_rate,
    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate,
    COUNTIF(response_valid) / COUNT(*) AS validation_pass_rate
FROM request_metrics
GROUP BY day, tenant_id, model_id, provider, task_type;

-- Add refresh policy for continuous aggregates
SELECT add_continuous_aggregate_policy('model_daily_stats', 
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Hourly tenant stats for real-time monitoring
CREATE MATERIALIZED VIEW tenant_hourly_stats AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    tenant_id,
    COUNT(*) AS request_count,
    AVG(latency_ms) AS avg_latency,
    SUM(cost_usd) AS total_cost,
    COUNTIF(success) / COUNT(*) AS success_rate,
    COUNTIF(cache_hit) / COUNT(*) AS cache_hit_rate,
    AVG(quality_score) AS avg_quality,
    COUNT(DISTINCT user_id) AS unique_users,
    COUNT(DISTINCT model_id) AS unique_models
FROM request_metrics
GROUP BY hour, tenant_id;

SELECT add_continuous_aggregate_policy('tenant_hourly_stats',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes');

-- =============================================================================
-- POSTGRESQL SCHEMAS (Core Data)
-- =============================================================================

-- Model Registry
CREATE TABLE IF NOT EXISTS model_profiles (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    
    -- Model capabilities
    context_window INT,
    estimated_cost_input_per_1k FLOAT,
    estimated_cost_output_per_1k FLOAT,
    
    -- Classification
    capabilities TEXT[],  -- ARRAY of capabilities
    quality_tier VARCHAR(20),  -- low, medium, high
    model_category VARCHAR(50),  -- local, standard, premium
    
    -- Benchmark results
    benchmark_results JSONB,
    reasoning_score FLOAT,
    code_score FLOAT,
    analysis_score FLOAT,
    creative_score FLOAT,
    
    -- Health and availability
    is_available BOOLEAN DEFAULT true,
    last_health_check TIMESTAMP,
    health_check_failures INT DEFAULT 0,
    
    -- Discovery metadata
    discovered_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    last_tested TIMESTAMP,
    discovery_source VARCHAR(50),  -- auto, manual, api
    
    -- Usage statistics
    total_requests BIGINT DEFAULT 0,
    total_cost_usd FLOAT DEFAULT 0,
    avg_quality_score FLOAT,
    
    -- Constraints
    CONSTRAINT model_profiles_unique UNIQUE (provider, model_id)
);

-- Learned Mappings (ML-driven model selection)
CREATE TABLE IF NOT EXISTS learned_mappings (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    
    -- Performance metrics
    avg_latency_ms FLOAT,
    p95_latency_ms FLOAT,
    p99_latency_ms FLOAT,
    avg_quality_score FLOAT,
    avg_cost_usd FLOAT,
    success_rate FLOAT,
    cache_hit_rate FLOAT,
    
    -- Learning metrics
    efficiency_score FLOAT,
    rank_in_category INT,
    preference_score FLOAT,
    
    -- Statistical confidence
    sample_count INT,
    confidence FLOAT,
    variance FLOAT,
    
    -- Thompson sampling parameters
    alpha FLOAT DEFAULT 1.0,
    beta FLOAT DEFAULT 1.0,
    
    -- Metadata
    last_trained TIMESTAMP DEFAULT NOW(),
    training_window_days INT DEFAULT 30,
    model_version VARCHAR(20),
    
    -- Constraints
    CONSTRAINT learned_mappings_unique UNIQUE (task_type, model_id)
);

-- Tenants (Multi-tenancy)
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id VARCHAR(255) PRIMARY KEY,
    tenant_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    tenant_type VARCHAR(50) DEFAULT 'standard',
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Database isolation
    db_schema VARCHAR(255),
    vector_db_namespace VARCHAR(255),
    
    -- Budget limits
    monthly_budget_usd FLOAT DEFAULT 1000,
    daily_budget_usd FLOAT DEFAULT 50,
    
    -- Status
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Contacts
    admin_email VARCHAR(255),
    billing_contact VARCHAR(255),
    security_contact VARCHAR(255)
);

-- Budget Tracking (Hierarchical)
CREATE TABLE IF NOT EXISTS budget_tracking (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    team_id VARCHAR(255),
    project_id VARCHAR(255),
    level VARCHAR(20) NOT NULL,  -- tenant, team, project
    
    -- Period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Budget limits
    limit_usd FLOAT NOT NULL,
    spent_usd FLOAT DEFAULT 0,
    
    -- Alerts
    warning_threshold_pct FLOAT DEFAULT 80,
    critical_threshold_pct FLOAT DEFAULT 95,
    last_alert_sent TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT budget_tracking_unique UNIQUE (tenant_id, team_id, project_id, level, period_start),
    CONSTRAINT budget_tracking_level_check CHECK (level IN ('tenant', 'team', 'project'))
);

-- Budget Configurations
CREATE TABLE IF NOT EXISTS budget_configs (
    id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    level VARCHAR(20) NOT NULL,
    team_id VARCHAR(255),
    project_id VARCHAR(255),
    
    -- Limits
    monthly_limit_usd FLOAT NOT NULL,
    daily_limit_usd FLOAT NOT NULL,
    
    -- Thresholds
    warning_threshold_pct FLOAT DEFAULT 80,
    critical_threshold_pct FLOAT DEFAULT 95,
    
    -- Actions
    action_on_exceed VARCHAR(50) DEFAULT 'downgrade_to_local',
    
    -- Notifications
    alert_emails TEXT[],
    slack_webhook VARCHAR(500),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT budget_configs_unique UNIQUE (tenant_id, team_id, project_id, level),
    CONSTRAINT budget_configs_level_check CHECK (level IN ('tenant', 'team', 'project'))
);

-- Budget Alerts
CREATE TABLE IF NOT EXISTS budget_alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(255) NOT NULL,
    level VARCHAR(20) NOT NULL,
    team_id VARCHAR(255),
    project_id VARCHAR(255),
    
    -- Alert details
    alert_type VARCHAR(50) NOT NULL,  -- threshold_warning, threshold_critical, budget_exceeded
    current_spend_usd FLOAT NOT NULL,
    limit_usd FLOAT NOT NULL,
    threshold_pct FLOAT NOT NULL,
    
    -- Status
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    notification_sent BOOLEAN DEFAULT false,
    status VARCHAR(20) DEFAULT 'active',
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT budget_alerts_type_check CHECK (alert_type IN ('threshold_warning', 'threshold_critical', 'budget_exceeded', 'daily_limit_exceeded'))
);

-- Audit Logs (Append-only for compliance)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Context
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    request_id UUID,
    session_id VARCHAR(255),
    
    -- Event details
    action VARCHAR(100) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    
    -- Resource information
    model_id VARCHAR(255),
    task_type VARCHAR(50),
    team_id VARCHAR(255),
    project_id VARCHAR(255),
    
    -- Metrics
    cost_usd FLOAT,
    latency_ms FLOAT,
    token_count INT,
    
    -- Network information
    ip_address VARCHAR(45),
    user_agent TEXT,
    endpoint VARCHAR(255),
    
    -- Result
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    error_type VARCHAR(50),
    
    -- Compliance
    data_classification VARCHAR(50),
    retention_days INT DEFAULT 2555,  -- 7 years
    
    -- Additional metadata
    metadata JSONB DEFAULT '{}',
    
    -- Integrity
    event_hash VARCHAR(64),  -- SHA-256 hash for integrity
    
    -- Constraints
    CONSTRAINT audit_logs_action_check CHECK (action IN (
        'login', 'logout', 'permission_check',
        'model_selected', 'model_invoked', 'model_failed',
        'budget_check', 'budget_exceeded', 'spending_recorded',
        'cache_hit', 'cache_miss', 'cache_store',
        'config_updated', 'policy_changed', 'tenant_created', 'tenant_deleted',
        'data_accessed', 'data_exported', 'data_deleted',
        'unauthorized_access', 'security_violation', 'suspicious_activity'
    )),
    CONSTRAINT audit_logs_severity_check CHECK (severity IN ('info', 'warning', 'error', 'critical'))
);

-- Create trigger to prevent updates/deletes on audit logs (immutable)
CREATE OR REPLACE FUNCTION audit_logs_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit logs are append-only and cannot be modified';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_immutable_trigger
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION audit_logs_immutable();

-- Cached Responses
CREATE TABLE IF NOT EXISTS cached_responses (
    cache_key VARCHAR(255) PRIMARY KEY,
    original_prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    
    -- Quality and cost
    cost_saved FLOAT,
    quality_score FLOAT,
    similarity_threshold FLOAT,
    
    -- Usage tracking
    hit_count INT DEFAULT 0,
    last_hit TIMESTAMP,
    
    -- Timestamps
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Vector Embeddings (for semantic cache)
CREATE TABLE IF NOT EXISTS prompt_embeddings (
    cache_key VARCHAR(255) PRIMARY KEY,
    embedding vector(384),  -- Using all-MiniLM-L6-v2
    task_type VARCHAR(50),
    quality_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Create vector index for similarity search
CREATE INDEX idx_prompt_embeddings_vector ON prompt_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Optimization Recommendations
CREATE TABLE IF NOT EXISTS optimization_recommendations (
    recommendation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(255) NOT NULL,
    
    -- Recommendation details
    recommendation_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    impact_estimate TEXT,
    savings_estimate_usd FLOAT,
    
    -- Target
    target_model_id VARCHAR(255),
    target_task_type VARCHAR(50),
    target_team_id VARCHAR(255),
    target_project_id VARCHAR(255),
    
    -- Metrics
    current_metrics JSONB DEFAULT '{}',
    projected_metrics JSONB DEFAULT '{}',
    
    -- Confidence and priority
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    priority VARCHAR(20) DEFAULT 'medium',
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    implemented_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT recommendations_type_check CHECK (recommendation_type IN (
        'retire_model', 'downgrade_to_local', 'enable_cache', 
        'adjust_policy', 'increase_budget', 'optimize_task_routing'
    )),
    CONSTRAINT recommendations_priority_check CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT recommendations_status_check CHECK (status IN ('pending', 'accepted', 'rejected', 'implemented'))
);

-- Provider Health Status
CREATE TABLE IF NOT EXISTS provider_health (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    model_id VARCHAR(255),
    
    -- Health status
    status VARCHAR(20) DEFAULT 'healthy',  -- healthy, degraded, unhealthy, unknown
    last_check TIMESTAMP DEFAULT NOW(),
    consecutive_failures INT DEFAULT 0,
    
    -- Performance metrics
    avg_latency_ms FLOAT,
    success_rate FLOAT,
    error_rate FLOAT,
    
    -- Issues
    last_error TEXT,
    error_type VARCHAR(50),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT provider_health_unique UNIQUE (provider, model_id),
    CONSTRAINT provider_health_status_check CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'unknown'))
);

-- Feature Flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id SERIAL PRIMARY KEY,
    flag_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    
    -- Flag state
    enabled BOOLEAN DEFAULT false,
    rollout_percentage FLOAT DEFAULT 0,  -- 0-100 for gradual rollout
    
    -- Targeting
    tenant_ids TEXT[],  -- Specific tenants
    user_ids TEXT[],    -- Specific users
    conditions JSONB,   -- Complex conditions
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(255),
    
    -- Constraints
    CONSTRAINT feature_flags_rollout_check CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100)
);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Tenant overview view
CREATE OR REPLACE VIEW tenant_overview AS
SELECT 
    t.tenant_id,
    t.tenant_name,
    t.display_name,
    t.tenant_type,
    t.status,
    t.created_at,
    
    -- Budget info
    COALESCE(bt.monthly_limit_usd, t.monthly_budget_usd) as monthly_budget,
    COALESCE(bt.spent_usd, 0) as current_spend,
    CASE 
        WHEN bt.spent_usd IS NOT NULL THEN 
            (bt.spent_usd / bt.monthly_limit_usd * 100)
        ELSE 0 
    END as budget_usage_pct,
    
    -- Usage stats (last 30 days)
    COALESCE(stats.request_count, 0) as requests_30d,
    COALESCE(stats.unique_users, 0) as unique_users_30d,
    COALESCE(stats.avg_quality, 0) as avg_quality_30d,
    COALESCE(stats.total_cost, 0) as total_cost_30d,
    
    -- Model usage
    COALESCE(stats.unique_models, 0) as models_used_30d
    
FROM tenants t
LEFT JOIN LATERAL (
    SELECT 
        limit_usd as monthly_limit_usd,
        spent_usd
    FROM budget_tracking 
    WHERE tenant_id = t.tenant_id 
        AND level = 'tenant' 
        AND period_start = date_trunc('month', CURRENT_DATE)
    ORDER BY period_start DESC 
    LIMIT 1
) bt ON true
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as request_count,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(quality_score) as avg_quality,
        SUM(cost_usd) as total_cost,
        COUNT(DISTINCT model_id) as unique_models
    FROM request_metrics 
    WHERE tenant_id = t.tenant_id 
        AND time >= NOW() - INTERVAL '30 days'
) stats ON true;

-- Model performance view
CREATE OR REPLACE VIEW model_performance AS
SELECT 
    mp.provider,
    mp.model_id,
    mp.display_name,
    mp.quality_tier,
    mp.is_available,
    mp.total_requests,
    mp.total_cost_usd,
    mp.avg_quality_score,
    
    -- Recent performance (last 7 days)
    COALESCE(recent.request_count, 0) as requests_7d,
    COALESCE(recent.avg_latency, 0) as avg_latency_7d,
    COALESCE(recent.success_rate, 0) as success_rate_7d,
    COALESCE(recent.avg_quality, 0) as avg_quality_7d,
    COALESCE(recent.total_cost, 0) as total_cost_7d,
    
    -- Health status
    COALESCE(ph.status, 'unknown') as health_status,
    ph.last_check as last_health_check,
    ph.consecutive_failures
    
FROM model_profiles mp
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as request_count,
        AVG(latency_ms) as avg_latency,
        COUNTIF(success) / COUNT(*) as success_rate,
        AVG(quality_score) as avg_quality,
        SUM(cost_usd) as total_cost
    FROM request_metrics 
    WHERE provider = mp.provider 
        AND model_id = mp.model_id 
        AND time >= NOW() - INTERVAL '7 days'
) recent ON true
LEFT JOIN provider_health ph ON ph.provider = mp.provider AND ph.model_id = mp.model_id;

-- =============================================================================
-- FUNCTIONS AND TRIGGERS
# =============================================================================

-- Function to update model statistics
CREATE OR REPLACE FUNCTION update_model_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update total requests and cost for the model
    UPDATE model_profiles 
    SET 
        total_requests = total_requests + 1,
        total_cost_usd = total_cost_usd + COALESCE(NEW.cost_usd, 0),
        avg_quality_score = (
            SELECT AVG(quality_score) 
            FROM request_metrics 
            WHERE provider = NEW.provider AND model_id = NEW.model_id
        ),
        last_updated = NOW()
    WHERE provider = NEW.provider AND model_id = NEW.model_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to update model stats on each request
CREATE TRIGGER update_model_stats_trigger
    AFTER INSERT ON request_metrics
    FOR EACH ROW
    EXECUTE FUNCTION update_model_stats();

-- Function to check budget constraints
CREATE OR REPLACE FUNCTION check_budget_constraint(
    p_tenant_id VARCHAR(255),
    p_estimated_cost FLOAT,
    p_team_id VARCHAR DEFAULT NULL,
    p_project_id VARCHAR DEFAULT NULL
)
RETURNS TABLE(
    within_budget BOOLEAN,
    warnings TEXT[],
    actions TEXT[]
) AS $$
DECLARE
    v_monthly_limit FLOAT;
    v_monthly_spent FLOAT;
    v_daily_limit FLOAT;
    v_daily_spent FLOAT;
    v_warnings TEXT[] := '{}';
    v_actions TEXT[] := '{}';
BEGIN
    -- Get tenant budget limits
    SELECT monthly_limit_usd, daily_limit_usd 
    INTO v_monthly_limit, v_daily_limit
    FROM budget_configs 
    WHERE tenant_id = p_tenant_id AND level = 'tenant';
    
    -- Get current spending
    SELECT COALESCE(SUM(spent_usd), 0)
    INTO v_monthly_spent
    FROM budget_tracking 
    WHERE tenant_id = p_tenant_id 
        AND level = 'tenant' 
        AND period_start = date_trunc('month', CURRENT_DATE);
    
    -- Estimate daily spend (simplified)
    v_daily_spent := v_monthly_spent / EXTRACT(DAY FROM CURRENT_DATE);
    
    -- Check monthly budget
    IF v_monthly_spent + p_estimated_cost > v_monthly_limit THEN
        v_warnings := array_append(v_warnings, 'Monthly budget will be exceeded');
        v_actions := array_append(v_actions, 'downgrade_to_local');
        RETURN QUERY SELECT false, v_warnings, v_actions;
    ELSIF v_monthly_spent + p_estimated_cost > v_monthly_limit * 0.8 THEN
        v_warnings := array_append(v_warnings, 'Approaching monthly budget limit');
        v_actions := array_append(v_actions, 'monitor_closely');
    END IF;
    
    -- Check daily budget
    IF v_daily_spent + p_estimated_cost > v_daily_limit THEN
        v_warnings := array_append(v_warnings, 'Daily budget will be exceeded');
        v_actions := array_append(v_actions, 'downgrade_to_local');
        RETURN QUERY SELECT false, v_warnings, v_actions;
    ELSIF v_daily_spent + p_estimated_cost > v_daily_limit * 0.8 THEN
        v_warnings := array_append(v_warnings, 'Approaching daily budget limit');
    END IF;
    
    RETURN QUERY SELECT true, v_warnings, v_actions;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- INDEXES FOR PERFORMANCE
# =============================================================================

-- Additional indexes for common queries
CREATE INDEX idx_audit_logs_tenant_time ON audit_logs (tenant_id, timestamp DESC);
CREATE INDEX idx_audit_logs_action_time ON audit_logs (action, timestamp DESC);
CREATE INDEX idx_audit_logs_user_time ON audit_logs (user_id, timestamp DESC) WHERE user_id IS NOT NULL;

CREATE INDEX idx_cached_responses_task_model ON cached_responses (task_type, model_id);
CREATE INDEX idx_cached_responses_expires ON cached_responses (expires_at) WHERE expires_at IS NOT NULL;

CREATE INDEX idx_recommendations_tenant_status ON optimization_recommendations (tenant_id, status);
CREATE INDEX idx_recommendations_type_priority ON optimization_recommendations (recommendation_type, priority);

CREATE INDEX idx_learned_mappings_task_confidence ON learned_mappings (task_type, confidence DESC);
CREATE INDEX idx_model_profiles_available ON model_profiles (is_available) WHERE is_available = true;

-- =============================================================================
-- SAMPLE DATA (for development)
# =============================================================================

-- Insert sample tenant
INSERT INTO tenants (tenant_id, tenant_name, display_name, config) VALUES
('default', 'Default Tenant', 'Default', '{"allowed_models": [], "blocked_models": []}')
ON CONFLICT (tenant_id) DO NOTHING;

-- Insert sample budget config
INSERT INTO budget_configs (tenant_id, level, monthly_limit_usd, daily_limit_usd) VALUES
('default', 'tenant', 1000, 50)
ON CONFLICT (tenant_id, team_id, project_id, level) DO NOTHING;

-- Insert sample feature flags
INSERT INTO feature_flags (flag_name, description, enabled) VALUES
('auto_discovery', 'Automatic model discovery', true),
('semantic_cache', 'Semantic caching of responses', true),
('response_validation', 'Response quality validation', true),
('budget_management', 'Budget tracking and enforcement', true),
('audit_logging', 'Comprehensive audit logging', true)
ON CONFLICT (flag_name) DO NOTHING;
