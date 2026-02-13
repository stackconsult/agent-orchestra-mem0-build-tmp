"""
Multi-Tenancy Management

Provides tenant isolation and context management for enterprise deployments.
Supports hierarchical tenant organization with complete data isolation.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Context variable for current tenant
current_tenant: ContextVar[Optional['TenantContext']] = ContextVar('current_tenant', default=None)


class TenantStatus(Enum):
    """Tenant lifecycle status."""
    ACTIVE = "active"
    INACTIVE = "inactive" 
    SUSPENDED = "suspended"
    PENDING = "pending"


@dataclass
class TenantConfig:
    """Tenant-specific configuration."""
    tenant_id: str
    tenant_name: str
    display_name: str
    
    # Model restrictions
    allowed_models: List[str] = field(default_factory=list)  # empty = all
    blocked_models: List[str] = field(default_factory=list)
    
    # Budget limits
    monthly_budget_usd: float = 1000.0
    daily_budget_usd: float = 50.0
    
    # Policy customization
    custom_policy_weights: Optional[Dict[str, float]] = None
    
    # Data residency
    data_region: str = "us-east"
    db_schema: Optional[str] = None
    vector_db_namespace: Optional[str] = None
    
    # Feature flags
    enable_semantic_cache: bool = True
    enable_response_validation: bool = True
    enable_audit_logging: bool = True
    
    # Contact info
    admin_email: Optional[str] = None
    billing_contact: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TenantContext:
    """Runtime context for tenant operations."""
    tenant_id: str
    tenant_config: TenantConfig
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Runtime state
    current_monthly_spend: float = 0.0
    current_daily_spend: float = 0.0
    
    # Database session for this tenant
    db_session: Optional[AsyncSession] = None
    
    def __post_init__(self):
        if not self.request_id:
            self.request_id = str(uuid.uuid4())


class MultiTenancyManager:
    """Manages multi-tenant operations with complete data isolation."""
    
    def __init__(self, db_url: str, vector_db_config: Dict[str, Any]):
        """Initialize multi-tenancy manager."""
        self.db_url = db_url
        self.vector_db_config = vector_db_config
        
        # Database engine (shared)
        self.engine = create_async_engine(db_url, echo=False)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
        # Tenant configurations cache
        self._tenant_configs: Dict[str, TenantConfig] = {}
        self._tenant_schemas: Dict[str, str] = {}
        
        # Vector DB connections per tenant
        self._vector_db_clients: Dict[str, Any] = {}
        
        logger.info("MultiTenancyManager initialized")
    
    async def initialize(self):
        """Initialize multi-tenancy system."""
        # Create default tenant if not exists
        await self._ensure_default_tenant()
        
        # Load existing tenant configurations
        await self._load_tenant_configs()
        
        logger.info("MultiTenancyManager initialization complete")
    
    async def create_tenant(self, config: TenantConfig) -> TenantContext:
        """Create a new tenant with complete isolation."""
        try:
            # Generate unique schema name
            schema_name = f"tenant_{config.tenant_id.replace('-', '_')}"
            config.db_schema = schema_name
            config.vector_db_namespace = f"tenant_{config.tenant_id}"
            
            # Create tenant schema
            await self._create_tenant_schema(schema_name)
            
            # Create vector DB namespace
            await self._create_vector_namespace(config.vector_db_namespace)
            
            # Store tenant configuration
            await self._store_tenant_config(config)
            
            # Cache configuration
            self._tenant_configs[config.tenant_id] = config
            self._tenant_schemas[config.tenant_id] = schema_name
            
            # Create tenant context
            context = TenantContext(
                tenant_id=config.tenant_id,
                tenant_config=config
            )
            
            logger.info(f"Created tenant: {config.tenant_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create tenant {config.tenant_id}: {e}")
            raise
    
    async def get_tenant_context(self, tenant_id: str, user_id: Optional[str] = None) -> Optional[TenantContext]:
        """Get tenant context for operations."""
        try:
            # Get tenant configuration
            config = self._tenant_configs.get(tenant_id)
            if not config:
                # Try loading from database
                config = await self._load_tenant_config(tenant_id)
                if not config:
                    return None
            
            # Create tenant-specific database session
            schema_name = self._tenant_schemas.get(tenant_id)
            db_session = await self._create_tenant_session(schema_name)
            
            # Get current spending
            monthly_spend, daily_spend = await self._get_tenant_spending(tenant_id)
            
            context = TenantContext(
                tenant_id=tenant_id,
                tenant_config=config,
                user_id=user_id,
                db_session=db_session,
                current_monthly_spend=monthly_spend,
                current_daily_spend=daily_spend
            )
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get tenant context for {tenant_id}: {e}")
            return None
    
    async def update_tenant_config(self, tenant_id: str, updates: Dict[str, Any]) -> bool:
        """Update tenant configuration."""
        try:
            config = self._tenant_configs.get(tenant_id)
            if not config:
                return False
            
            # Update configuration
            for key, value in updates.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            config.updated_at = datetime.utcnow()
            
            # Store updated configuration
            await self._store_tenant_config(config)
            
            # Update cache
            self._tenant_configs[tenant_id] = config
            
            logger.info(f"Updated tenant config: {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update tenant config {tenant_id}: {e}")
            return False
    
    async def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant and all associated data."""
        try:
            # Get tenant info
            config = self._tenant_configs.get(tenant_id)
            if not config:
                return False
            
            # Drop tenant schema
            schema_name = self._tenant_schemas.get(tenant_id)
            if schema_name:
                await self._drop_tenant_schema(schema_name)
            
            # Delete vector DB namespace
            if config.vector_db_namespace:
                await self._delete_vector_namespace(config.vector_db_namespace)
            
            # Remove from cache
            self._tenant_configs.pop(tenant_id, None)
            self._tenant_schemas.pop(tenant_id, None)
            
            # Delete from database
            await self._delete_tenant_config(tenant_id)
            
            logger.info(f"Deleted tenant: {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete tenant {tenant_id}: {e}")
            return False
    
    async def list_tenants(self) -> List[TenantConfig]:
        """List all tenant configurations."""
        return list(self._tenant_configs.values())
    
    async def _ensure_default_tenant(self):
        """Ensure default tenant exists."""
        if "default" not in self._tenant_configs:
            default_config = TenantConfig(
                tenant_id="default",
                tenant_name="Default Tenant",
                display_name="Default"
            )
            await self.create_tenant(default_config)
    
    async def _create_tenant_schema(self, schema_name: str):
        """Create database schema for tenant."""
        # Validate schema name to prevent SQL injection
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', schema_name):
            raise ValueError(f"Invalid schema name: {schema_name}")
        
        async with self.engine.begin() as conn:
            # Use parameterized queries for schema operations
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS :schema_name"), {"schema_name": schema_name})
            # Grant permissions
            await conn.execute(text("GRANT ALL ON SCHEMA :schema_name TO current_user"), {"schema_name": schema_name})
    
    async def _drop_tenant_schema(self, schema_name: str):
        """Drop tenant database schema."""
        # Validate schema name to prevent SQL injection
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', schema_name):
            raise ValueError(f"Invalid schema name: {schema_name}")
        
        async with self.engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA IF EXISTS :schema_name CASCADE"), {"schema_name": schema_name})
    
    async def _create_tenant_session(self, schema_name: Optional[str]) -> AsyncSession:
        """Create database session for tenant."""
        session = self.session_factory()
        if schema_name:
            # Validate schema name to prevent SQL injection
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', schema_name):
                raise ValueError(f"Invalid schema name: {schema_name}")
            # Set search_path to tenant schema
            await session.execute(text("SET search_path TO :schema_name, public"), {"schema_name": schema_name})
        return session
    
    async def _create_vector_namespace(self, namespace: str):
        """Create vector DB namespace for tenant."""
        # Implementation depends on vector DB (Weaviate/Pinecone)
        # This is a placeholder for the actual implementation
        logger.info(f"Creating vector namespace: {namespace}")
    
    async def _delete_vector_namespace(self, namespace: str):
        """Delete vector DB namespace."""
        # Implementation depends on vector DB
        logger.info(f"Deleting vector namespace: {namespace}")
    
    async def _store_tenant_config(self, config: TenantConfig):
        """Store tenant configuration in database."""
        async with self.session_factory() as session:
            # Upsert tenant configuration
            query = text("""
                INSERT INTO tenants (tenant_id, tenant_name, config, created_at, updated_at)
                VALUES (:tenant_id, :tenant_name, :config, :created_at, :updated_at)
                ON CONFLICT (tenant_id) DO UPDATE SET
                    tenant_name = EXCLUDED.tenant_name,
                    config = EXCLUDED.config,
                    updated_at = EXCLUDED.updated_at
            """)
            
            await session.execute(query, {
                "tenant_id": config.tenant_id,
                "tenant_name": config.tenant_name,
                "config": config.__dict__,
                "created_at": config.created_at,
                "updated_at": config.updated_at
            })
            await session.commit()
    
    async def _load_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """Load tenant configuration from database."""
        async with self.session_factory() as session:
            query = text("SELECT config FROM tenants WHERE tenant_id = :tenant_id")
            result = await session.execute(query, {"tenant_id": tenant_id})
            row = result.fetchone()
            
            if row:
                config_dict = row.config
                config = TenantConfig(**config_dict)
                self._tenant_configs[tenant_id] = config
                return config
            return None
    
    async def _load_tenant_configs(self):
        """Load all tenant configurations."""
        async with self.session_factory() as session:
            query = text("SELECT tenant_id, config FROM tenants")
            result = await session.execute(query)
            
            for row in result:
                config_dict = row.config
                config = TenantConfig(**config_dict)
                self._tenant_configs[config.tenant_id] = config
    
    async def _delete_tenant_config(self, tenant_id: str):
        """Delete tenant configuration from database."""
        async with self.session_factory() as session:
            query = text("DELETE FROM tenants WHERE tenant_id = :tenant_id")
            await session.execute(query, {"tenant_id": tenant_id})
            await session.commit()
    
    async def _get_tenant_spending(self, tenant_id: str) -> tuple[float, float]:
        """Get current tenant spending."""
        # This would query budget_tracking table
        # For now, return zeros
        return 0.0, 0.0
    
    async def close(self):
        """Close all connections."""
        await self.engine.dispose()
        logger.info("MultiTenancyManager closed")


# Tenant middleware for FastAPI
class TenantMiddleware:
    """FastAPI middleware for tenant identification."""
    
    def __init__(self, app, tenancy_manager: MultiTenancyManager):
        self.app = app
        self.tenancy_manager = tenancy_manager
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware implementation."""
        if scope["type"] == "http":
            # Extract tenant from headers or subdomain
            headers = dict(scope.get("headers", []))
            tenant_id = headers.get(b"x-tenant-id", b"default").decode()
            
            # Get tenant context
            context = await self.tenancy_manager.get_tenant_context(tenant_id)
            if context:
                # Set in context variable
                current_tenant.set(context)
                
                # Add tenant info to scope
                scope["tenant"] = context
        
        await self.app(scope, receive, send)


def get_current_tenant() -> Optional[TenantContext]:
    """Get current tenant from context."""
    return current_tenant.get()
