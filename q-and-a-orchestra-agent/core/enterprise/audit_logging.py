"""
Audit Logging

Provides comprehensive audit trails for compliance and security.
Supports SOC 2, HIPAA, GDPR compliance with immutable logging.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import uuid
import hashlib
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_
import httpx

from .multi_tenancy import TenantContext, get_current_tenant

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Audit event action types."""
    # Authentication & Authorization
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHECK = "permission_check"
    
    # Model Operations
    MODEL_SELECTED = "model_selected"
    MODEL_INVOKED = "model_invoked"
    MODEL_FAILED = "model_failed"
    
    # Budget Operations
    BUDGET_CHECK = "budget_check"
    BUDGET_EXCEEDED = "budget_exceeded"
    SPENDING_RECORDED = "spending_recorded"
    
    # Cache Operations
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_STORE = "cache_store"
    
    # Configuration
    CONFIG_UPDATED = "config_updated"
    POLICY_CHANGED = "policy_changed"
    TENANT_CREATED = "tenant_created"
    TENANT_DELETED = "tenant_deleted"
    
    # Data Operations
    DATA_ACCESSED = "data_accessed"
    DATA_EXPORTED = "data_exported"
    DATA_DELETED = "data_deleted"
    
    # Security Events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SECURITY_VIOLATION = "security_violation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit log event."""
    # Core fields
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    tenant_id: str = ""
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    
    # Event details
    action: AuditAction = AuditAction.MODEL_INVOKED
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Resource information
    model_id: Optional[str] = None
    task_type: Optional[str] = None
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Metrics
    cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None
    
    # Network information
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    
    # Result
    success: bool = True
    error_message: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Compliance fields
    data_classification: Optional[str] = None  # PII, PHI, etc.
    retention_days: int = 2555  # 7 years default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert enums to strings
        result["action"] = self.action.value
        result["severity"] = self.severity.value
        # Convert datetime to ISO format
        result["timestamp"] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    def get_hash(self) -> str:
        """Get SHA-256 hash for integrity verification."""
        event_json = self.to_json()
        return hashlib.sha256(event_json.encode()).hexdigest()


class AuditLogger:
    """Comprehensive audit logging system."""
    
    def __init__(
        self,
        db_session_factory,
        siem_config: Optional[Dict[str, Any]] = None,
        retention_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize audit logger."""
        self.session_factory = db_session_factory
        self.siem_config = siem_config or {}
        self.retention_config = retention_config or {}
        
        # Batch processing for performance
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._batch_size = 100
        self._batch_timeout = 5.0  # seconds
        
        # Background task
        self._background_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("AuditLogger initialized")
    
    async def start(self):
        """Start audit logging background processing."""
        if self._running:
            return
        
        self._running = True
        self._background_task = asyncio.create_task(self._process_events())
        logger.info("AuditLogger started")
    
    async def stop(self):
        """Stop audit logging and flush remaining events."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background task
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining events
        await self._flush_queue()
        
        logger.info("AuditLogger stopped")
    
    async def log_event(self, event: AuditEvent) -> bool:
        """Log an audit event."""
        try:
            # Enrich event with context if available
            await self._enrich_event(event)
            
            # Add to queue for batch processing
            await self._event_queue.put(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return False
    
    async def log_action(
        self,
        action: AuditAction,
        tenant_id: str,
        user_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Convenience method to log an action."""
        event = AuditEvent(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            **kwargs
        )
        return await self.log_event(event)
    
    async def query_events(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        severity: Optional[AuditSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[AuditEvent]:
        """Query audit events with filters."""
        try:
            async with self.session_factory() as session:
                # Build query using SQLAlchemy ORM operators instead of text()
                from sqlalchemy import desc
                
                # Start with base query
                query = select(AuditLog).order_by(desc(AuditLog.timestamp))
                
                # Apply filters using ORM operators
                conditions = []
                if tenant_id:
                    conditions.append(AuditLog.tenant_id == tenant_id)
                if user_id:
                    conditions.append(AuditLog.user_id == user_id)
                if action:
                    conditions.append(AuditLog.action == action.value)
                if severity:
                    conditions.append(AuditLog.severity == severity.value)
                if start_time:
                    conditions.append(AuditLog.timestamp >= start_time)
                if end_time:
                    conditions.append(AuditLog.timestamp <= end_time)
                if resource_type:
                    conditions.append(AuditLog.resource_type == resource_type)
                if ip_address:
                    conditions.append(AuditLog.ip_address == ip_address)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                # Apply pagination
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                rows = result.scalars().all()
                
                events = []
                for row in rows:
                    event = AuditEvent(
                        event_id=row.event_id,
                        timestamp=row.timestamp,
                        tenant_id=row.tenant_id,
                        user_id=row.user_id,
                        request_id=row.request_id,
                        session_id=row.session_id,
                        action=AuditAction(row.action),
                        severity=AuditSeverity(row.severity),
                        model_id=row.model_id,
                        task_type=row.task_type,
                        team_id=row.team_id,
                        project_id=row.project_id,
                        cost_usd=row.cost_usd,
                        latency_ms=row.latency_ms,
                        token_count=row.token_count,
                        ip_address=row.ip_address,
                        user_agent=row.user_agent,
                        endpoint=row.endpoint,
                        success=row.success,
                        error_message=row.error_message,
                        metadata=json.loads(row.metadata) if row.metadata else {},
                        data_classification=row.data_classification,
                        retention_days=row.retention_days
                    )
                    events.append(event)
                
                return events
                
        except Exception as e:
            logger.error(f"Error querying audit events: {e}")
            return []
    
    async def get_compliance_report(
        self,
        tenant_id: str,
        start_date: datetime,
        end_date: datetime,
        compliance_type: str = "SOC2"
    ) -> Dict[str, Any]:
        """Generate compliance report for a period."""
        try:
            # Get events for the period
            events = await self.query_events(
                tenant_id=tenant_id,
                start_time=start_date,
                end_time=end_date,
                limit=100000
            )
            
            # Analyze events
            report = {
                "tenant_id": tenant_id,
                "compliance_type": compliance_type,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "summary": {
                    "total_events": len(events),
                    "successful_events": sum(1 for e in events if e.success),
                    "failed_events": sum(1 for e in events if not e.success),
                    "critical_events": sum(1 for e in events if e.severity == AuditSeverity.CRITICAL),
                    "unique_users": len(set(e.user_id for e in events if e.user_id)),
                    "total_cost": sum(e.cost_usd or 0 for e in events),
                    "unique_models": len(set(e.model_id for e in events if e.model_id))
                },
                "breakdown": {
                    "by_action": {},
                    "by_severity": {},
                    "by_user": {},
                    "by_model": {},
                    "daily_counts": {}
                }
            }
            
            # Breakdown by action
            for event in events:
                action = event.action.value
                report["breakdown"]["by_action"][action] = report["breakdown"]["by_action"].get(action, 0) + 1
            
            # Breakdown by severity
            for event in events:
                severity = event.severity.value
                report["breakdown"]["by_severity"][severity] = report["breakdown"]["by_severity"].get(severity, 0) + 1
            
            # Breakdown by user
            for event in events:
                if event.user_id:
                    user = event.user_id
                    report["breakdown"]["by_user"][user] = report["breakdown"]["by_user"].get(user, 0) + 1
            
            # Breakdown by model
            for event in events:
                if event.model_id:
                    model = event.model_id
                    report["breakdown"]["by_model"][model] = report["breakdown"]["by_model"].get(model, 0) + 1
            
            # Daily counts
            for event in events:
                day = event.timestamp.date().isoformat()
                report["breakdown"]["daily_counts"][day] = report["breakdown"]["daily_counts"].get(day, 0) + 1
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {}
    
    async def _enrich_event(self, event: AuditEvent):
        """Enrich event with context information."""
        try:
            # Get current tenant context
            tenant_context = get_current_tenant()
            if tenant_context and not event.tenant_id:
                event.tenant_id = tenant_context.tenant_id
            
            # Add default retention if not set
            if event.retention_days == 2555:  # Default value
                retention = self.retention_config.get(event.action.value, 2555)
                event.retention_days = retention
            
        except Exception as e:
            logger.warning(f"Failed to enrich audit event: {e}")
    
    async def _process_events(self):
        """Background task to process events in batches."""
        while self._running:
            try:
                # Collect batch of events
                events = []
                try:
                    # Wait for first event with timeout
                    event = await asyncio.wait_for(self._event_queue.get(), timeout=self._batch_timeout)
                    events.append(event)
                    
                    # Get more events if available
                    while len(events) < self._batch_size and not self._event_queue.empty():
                        event = self._event_queue.get_nowait()
                        events.append(event)
                        
                except asyncio.TimeoutError:
                    # Process whatever we have
                    pass
                
                if events:
                    await self._store_events(events)
                    await self._send_to_siem(events)
                    
            except Exception as e:
                logger.error(f"Error in audit event processing: {e}")
                await asyncio.sleep(1)  # Brief pause before retry
    
    async def _store_events(self, events: List[AuditEvent]):
        """Store events in database."""
        try:
            async with self.session_factory() as session:
                for event in events:
                    query = text("""
                        INSERT INTO audit_logs (
                            event_id, timestamp, tenant_id, user_id, request_id, session_id,
                            action, severity, model_id, task_type, team_id, project_id,
                            cost_usd, latency_ms, token_count, ip_address, user_agent,
                            endpoint, success, error_message, metadata, data_classification,
                            retention_days, event_hash
                        )
                        VALUES (
                            :event_id, :timestamp, :tenant_id, :user_id, :request_id, :session_id,
                            :action, :severity, :model_id, :task_type, :team_id, :project_id,
                            :cost_usd, :latency_ms, :token_count, :ip_address, :user_agent,
                            :endpoint, :success, :error_message, :metadata, :data_classification,
                            :retention_days, :event_hash
                        )
                    """)
                    
                    await session.execute(query, {
                        "event_id": event.event_id,
                        "timestamp": event.timestamp,
                        "tenant_id": event.tenant_id,
                        "user_id": event.user_id,
                        "request_id": event.request_id,
                        "session_id": event.session_id,
                        "action": event.action.value,
                        "severity": event.severity.value,
                        "model_id": event.model_id,
                        "task_type": event.task_type,
                        "team_id": event.team_id,
                        "project_id": event.project_id,
                        "cost_usd": event.cost_usd,
                        "latency_ms": event.latency_ms,
                        "token_count": event.token_count,
                        "ip_address": event.ip_address,
                        "user_agent": event.user_agent,
                        "endpoint": event.endpoint,
                        "success": event.success,
                        "error_message": event.error_message,
                        "metadata": json.dumps(event.metadata) if event.metadata else None,
                        "data_classification": event.data_classification,
                        "retention_days": event.retention_days,
                        "event_hash": event.get_hash()
                    })
                
                await session.commit()
                logger.debug(f"Stored {len(events)} audit events")
                
        except Exception as e:
            logger.error(f"Failed to store audit events: {e}")
    
    async def _send_to_siem(self, events: List[AuditEvent]):
        """Send events to SIEM system."""
        if not self.siem_config:
            return
        
        try:
            # Format events for SIEM
            siem_events = []
            for event in events:
                siem_event = {
                    "timestamp": event.timestamp.isoformat(),
                    "source": "agent-orchestra-router",
                    "event_type": event.action.value,
                    "severity": event.severity.value,
                    "tenant_id": event.tenant_id,
                    "user_id": event.user_id,
                    "details": event.to_dict()
                }
                siem_events.append(siem_event)
            
            # Send to SIEM (implementation depends on SIEM type)
            if self.siem_config.get("type") == "splunk":
                await self._send_to_splunk(siem_events)
            elif self.siem_config.get("type") == "elasticsearch":
                await self._send_to_elasticsearch(siem_events)
            elif self.siem_config.get("type") == "webhook":
                await self._send_to_webhook(siem_events)
                
        except Exception as e:
            logger.error(f"Failed to send events to SIEM: {e}")
    
    async def _send_to_splunk(self, events: List[Dict[str, Any]]):
        """Send events to Splunk HTTP Event Collector."""
        url = self.siem_config.get("url")
        token = self.siem_config.get("token")
        
        if not url or not token:
            return
        
        headers = {
            "Authorization": f"Splunk {token}",
            "Content-Type": "application/json"
        }
        
        for event in events:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json={"event": event}
                    )
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to send event to Splunk: {e}")
    
    async def _send_to_elasticsearch(self, events: List[Dict[str, Any]]):
        """Send events to Elasticsearch."""
        url = self.siem_config.get("url")
        index = self.siem_config.get("index", "audit-events")
        
        if not url:
            return
        
        headers = {"Content-Type": "application/json"}
        
        for event in events:
            try:
                doc_url = f"{url}/{index}/_doc"
                async with httpx.AsyncClient() as client:
                    response = await client.post(doc_url, headers=headers, json=event)
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Failed to send event to Elasticsearch: {e}")
    
    async def _send_to_webhook(self, events: List[Dict[str, Any]]):
        """Send events to generic webhook."""
        url = self.siem_config.get("url")
        
        if not url:
            return
        
        headers = {"Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=events)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send events to webhook: {e}")
    
    async def _flush_queue(self):
        """Flush remaining events in queue."""
        events = []
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except asyncio.QueueEmpty:
                break
        
        if events:
            await self._store_events(events)
            await self._send_to_siem(events)


# Context manager for audit logging
@asynccontextmanager
async def audit_context(
    audit_logger: AuditLogger,
    action: AuditAction,
    tenant_id: str,
    user_id: Optional[str] = None,
    **kwargs
):
    """Context manager for audit logging with automatic success/failure tracking."""
    event = AuditEvent(
        action=action,
        tenant_id=tenant_id,
        user_id=user_id,
        **kwargs
    )
    
    start_time = datetime.now(timezone.utc)
    
    try:
        yield event
        
        # Mark as successful
        event.success = True
        event.latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
    except Exception as e:
        # Mark as failed
        event.success = False
        event.error_message = str(e)
        event.severity = AuditSeverity.ERROR
        raise
    
    finally:
        # Log the event
        await audit_logger.log_event(event)
