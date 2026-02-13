"""
Budget Management

Provides hierarchical budget tracking and enforcement for enterprise tenants.
Supports tenant → team → project budget levels with real-time monitoring.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
import uuid
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, and_, or_

from .multi_tenancy import TenantContext, get_current_tenant

logger = logging.getLogger(__name__)


class BudgetLevel(Enum):
    """Budget hierarchy levels."""
    TENANT = "tenant"
    TEAM = "team"
    PROJECT = "project"


class BudgetStatus(Enum):
    """Budget status indicators."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


class AlertType(Enum):
    """Budget alert types."""
    THRESHOLD_WARNING = "threshold_warning"
    THRESHOLD_CRITICAL = "threshold_critical"
    BUDGET_EXCEEDED = "budget_exceeded"
    DAILY_LIMIT_EXCEEDED = "daily_limit_exceeded"


@dataclass
class BudgetConfig:
    """Budget configuration for a specific level."""
    tenant_id: str
    level: BudgetLevel
    team_id: Optional[str] = None
    project_id: Optional[str] = None
    
    # Budget limits
    monthly_limit_usd: float = 1000.0
    daily_limit_usd: float = 50.0
    
    # Alert thresholds (percentage)
    warning_threshold_pct: float = 80.0
    critical_threshold_pct: float = 95.0
    
    # Actions when limits exceeded
    action_on_exceed: str = "downgrade_to_local"  # or "block_requests"
    
    # Notification settings
    alert_emails: List[str] = field(default_factory=list)
    slack_webhook: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BudgetAlert:
    """Budget alert notification."""
    alert_id: str
    tenant_id: str
    level: BudgetLevel
    team_id: Optional[str]
    project_id: Optional[str]
    alert_type: AlertType
    
    # Alert details
    current_spend_usd: float
    limit_usd: float
    threshold_pct: float
    
    # Metadata
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    notification_sent: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "alert_id": self.alert_id,
            "tenant_id": self.tenant_id,
            "level": self.level.value,
            "team_id": self.team_id,
            "project_id": self.project_id,
            "alert_type": self.alert_type.value,
            "current_spend_usd": self.current_spend_usd,
            "limit_usd": self.limit_usd,
            "threshold_pct": self.threshold_pct,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "notification_sent": self.notification_sent
        }


@dataclass
class BudgetStatus:
    """Current budget status for a level."""
    tenant_id: str
    level: BudgetLevel
    team_id: Optional[str]
    project_id: Optional[str]
    
    # Current spending
    current_monthly_spend: float = 0.0
    current_daily_spend: float = 0.0
    
    # Limits
    monthly_limit: float = 0.0
    daily_limit: float = 0.0
    
    # Status
    monthly_status: BudgetStatus = BudgetStatus.HEALTHY
    daily_status: BudgetStatus = BudgetStatus.HEALTHY
    
    # Percentages
    monthly_usage_pct: float = 0.0
    daily_usage_pct: float = 0.0
    
    # Recommendations
    recommended_actions: List[str] = field(default_factory=list)


class BudgetManager:
    """Manages hierarchical budget tracking and enforcement."""
    
    def __init__(self, db_session_factory, smtp_config: Optional[Dict[str, Any]] = None):
        """Initialize budget manager."""
        self.session_factory = db_session_factory
        self.smtp_config = smtp_config
        
        # Budget configurations cache
        self._budget_configs: Dict[str, BudgetConfig] = {}
        
        # Active alerts cache
        self._active_alerts: Dict[str, BudgetAlert] = {}
        
        logger.info("BudgetManager initialized")
    
    async def initialize(self):
        """Initialize budget management system."""
        # Load existing budget configurations
        await self._load_budget_configs()
        
        # Load active alerts
        await self._load_active_alerts()
        
        logger.info("BudgetManager initialization complete")
    
    async def create_budget_config(self, config: BudgetConfig) -> bool:
        """Create budget configuration."""
        try:
            # Generate unique key
            key = self._generate_budget_key(
                config.tenant_id, config.level, config.team_id, config.project_id
            )
            
            # Store in database
            await self._store_budget_config(config)
            
            # Cache configuration
            self._budget_configs[key] = config
            
            logger.info(f"Created budget config: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create budget config: {e}")
            return False
    
    async def check_budget_before_request(
        self, 
        tenant_context: TenantContext,
        estimated_cost_usd: float,
        team_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """Check if request is within budget limits."""
        warnings = []
        actions = []
        
        try:
            # Check project level (if specified)
            if project_id:
                project_ok, project_warnings, project_actions = await self._check_budget_level(
                    tenant_context.tenant_id, BudgetLevel.PROJECT, 
                    team_id, project_id, estimated_cost_usd
                )
                if not project_ok:
                    return False, warnings + project_warnings, actions + project_actions
                warnings.extend(project_warnings)
                actions.extend(project_actions)
            
            # Check team level (if specified)
            if team_id:
                team_ok, team_warnings, team_actions = await self._check_budget_level(
                    tenant_context.tenant_id, BudgetLevel.TEAM,
                    team_id, None, estimated_cost_usd
                )
                if not team_ok:
                    return False, warnings + team_warnings, actions + team_actions
                warnings.extend(team_warnings)
                actions.extend(team_actions)
            
            # Check tenant level (always)
            tenant_ok, tenant_warnings, tenant_actions = await self._check_budget_level(
                tenant_context.tenant_id, BudgetLevel.TENANT,
                None, None, estimated_cost_usd
            )
            if not tenant_ok:
                return False, warnings + tenant_warnings, actions + tenant_actions
            warnings.extend(tenant_warnings)
            actions.extend(tenant_actions)
            
            return True, warnings, actions
            
        except Exception as e:
            logger.error(f"Error checking budget: {e}")
            # Allow request on budget system error
            return True, ["Budget check failed - proceeding"], []
    
    async def record_spending(
        self,
        tenant_context: TenantContext,
        actual_cost_usd: float,
        team_id: Optional[str] = None,
        project_id: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        """Record actual spending after request completion."""
        try:
            # Record spending at all applicable levels
            levels = []
            
            if project_id:
                levels.append((BudgetLevel.PROJECT, team_id, project_id))
            if team_id:
                levels.append((BudgetLevel.TEAM, team_id, None))
            levels.append((BudgetLevel.TENANT, None, None))
            
            for level, level_team_id, level_project_id in levels:
                await self._record_spending_at_level(
                    tenant_context.tenant_id,
                    level,
                    level_team_id,
                    level_project_id,
                    actual_cost_usd,
                    request_id
                )
            
            # Check for new alerts
            await self._check_and_create_alerts(tenant_context.tenant_id)
            
        except Exception as e:
            logger.error(f"Error recording spending: {e}")
    
    async def get_budget_status(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Optional[BudgetStatus]:
        """Get current budget status for a level."""
        try:
            # Get budget configuration
            config = await self._get_budget_config(tenant_id, level, team_id, project_id)
            if not config:
                return None
            
            # Get current spending
            monthly_spend, daily_spend = await self._get_current_spending(
                tenant_id, level, team_id, project_id
            )
            
            # Calculate status
            monthly_pct = (monthly_spend / config.monthly_limit_usd * 100) if config.monthly_limit_usd > 0 else 0
            daily_pct = (daily_spend / config.daily_limit_usd * 100) if config.daily_limit_usd > 0 else 0
            
            monthly_status = self._calculate_budget_status(monthly_pct, config)
            daily_status = self._calculate_budget_status(daily_pct, config)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                monthly_pct, daily_pct, monthly_status, daily_status
            )
            
            return BudgetStatus(
                tenant_id=tenant_id,
                level=level,
                team_id=team_id,
                project_id=project_id,
                current_monthly_spend=monthly_spend,
                current_daily_spend=daily_spend,
                monthly_limit=config.monthly_limit_usd,
                daily_limit=config.daily_limit_usd,
                monthly_status=monthly_status,
                daily_status=daily_status,
                monthly_usage_pct=monthly_pct,
                daily_usage_pct=daily_pct,
                recommended_actions=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting budget status: {e}")
            return None
    
    async def get_active_alerts(self, tenant_id: str) -> List[BudgetAlert]:
        """Get active alerts for tenant."""
        return [alert for alert in self._active_alerts.values() if alert.tenant_id == tenant_id]
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        try:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.resolved_at = datetime.utcnow()
            
            # Update in database
            await self._update_alert(alert)
            
            # Remove from active alerts
            self._active_alerts.pop(alert_id, None)
            
            logger.info(f"Resolved alert: {alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resolving alert: {e}")
            return False
    
    async def _check_budget_level(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str],
        project_id: Optional[str],
        estimated_cost_usd: float
    ) -> Tuple[bool, List[str], List[str]]:
        """Check budget at a specific level."""
        warnings = []
        actions = []
        
        # Get budget configuration
        config = await self._get_budget_config(tenant_id, level, team_id, project_id)
        if not config:
            # No budget configured, allow request
            return True, warnings, actions
        
        # Get current spending
        monthly_spend, daily_spend = await self._get_current_spending(
            tenant_id, level, team_id, project_id
        )
        
        # Check daily limit
        projected_daily_spend = daily_spend + estimated_cost_usd
        daily_pct = (projected_daily_spend / config.daily_limit_usd * 100) if config.daily_limit_usd > 0 else 0
        
        if daily_pct >= 100:
            actions.append(config.action_on_exceed)
            return False, ["Daily budget exceeded"], [config.action_on_exceed]
        elif daily_pct >= config.critical_threshold_pct:
            warnings.append(f"Daily budget critical: {daily_pct:.1f}%")
            actions.append(config.action_on_exceed)
        elif daily_pct >= config.warning_threshold_pct:
            warnings.append(f"Daily budget warning: {daily_pct:.1f}%")
        
        # Check monthly limit
        projected_monthly_spend = monthly_spend + estimated_cost_usd
        monthly_pct = (projected_monthly_spend / config.monthly_limit_usd * 100) if config.monthly_limit_usd > 0 else 0
        
        if monthly_pct >= 100:
            actions.append(config.action_on_exceed)
            return False, ["Monthly budget exceeded"], [config.action_on_exceed]
        elif monthly_pct >= config.critical_threshold_pct:
            warnings.append(f"Monthly budget critical: {monthly_pct:.1f}%")
            actions.append(config.action_on_exceed)
        elif monthly_pct >= config.warning_threshold_pct:
            warnings.append(f"Monthly budget warning: {monthly_pct:.1f}%")
        
        return True, warnings, actions
    
    async def _record_spending_at_level(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str],
        project_id: Optional[str],
        cost_usd: float,
        request_id: Optional[str]
    ):
        """Record spending at a specific budget level."""
        async with self.session_factory() as session:
            # Get or create budget tracking record
            today = date.today()
            month_start = today.replace(day=1)
            
            query = text("""
                INSERT INTO budget_tracking (
                    tenant_id, team_id, project_id, level,
                    period_start, period_end, limit_usd, spent_usd
                )
                VALUES (:tenant_id, :team_id, :project_id, :level,
                        :period_start, :period_end, :limit_usd, :spent_usd)
                ON CONFLICT (tenant_id, team_id, project_id, level, period_start)
                DO UPDATE SET spent_usd = budget_tracking.spent_usd + :spent_usd
            """)
            
            await session.execute(query, {
                "tenant_id": tenant_id,
                "team_id": team_id,
                "project_id": project_id,
                "level": level.value,
                "period_start": month_start,
                "period_end": month_start.replace(month=month_start.month % 12 + 1, day=1) if month_start.month < 12 else month_start.replace(year=month_start.year + 1, month=1, day=1),
                "limit_usd": 0,  # Will be updated by budget config
                "spent_usd": cost_usd
            })
            await session.commit()
    
    async def _get_budget_config(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str],
        project_id: Optional[str]
    ) -> Optional[BudgetConfig]:
        """Get budget configuration for a level."""
        key = self._generate_budget_key(tenant_id, level, team_id, project_id)
        return self._budget_configs.get(key)
    
    async def _get_current_spending(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str],
        project_id: Optional[str]
    ) -> Tuple[float, float]:
        """Get current spending for a level."""
        async with self.session_factory() as session:
            today = date.today()
            month_start = today.replace(day=1)
            
            # Monthly spending
            monthly_query = text("""
                SELECT COALESCE(SUM(spent_usd), 0) as monthly_spend
                FROM budget_tracking
                WHERE tenant_id = :tenant_id
                  AND (:team_id IS NULL OR team_id = :team_id)
                  AND (:project_id IS NULL OR project_id = :project_id)
                  AND level = :level
                  AND period_start = :period_start
            """)
            
            result = await session.execute(monthly_query, {
                "tenant_id": tenant_id,
                "team_id": team_id,
                "project_id": project_id,
                "level": level.value,
                "period_start": month_start
            })
            monthly_spend = result.scalar() or 0.0
            
            # Daily spending (simplified - would need more granular tracking)
            daily_spend = monthly_spend / today.day  # Rough estimate
            
            return monthly_spend, daily_spend
    
    def _generate_budget_key(
        self,
        tenant_id: str,
        level: BudgetLevel,
        team_id: Optional[str],
        project_id: Optional[str]
    ) -> str:
        """Generate unique key for budget configuration."""
        parts = [tenant_id, level.value]
        if team_id:
            parts.append(team_id)
        if project_id:
            parts.append(project_id)
        return ":".join(parts)
    
    def _calculate_budget_status(self, usage_pct: float, config: BudgetConfig) -> BudgetStatus:
        """Calculate budget status from usage percentage."""
        if usage_pct >= 100:
            return BudgetStatus.EXCEEDED
        elif usage_pct >= config.critical_threshold_pct:
            return BudgetStatus.CRITICAL
        elif usage_pct >= config.warning_threshold_pct:
            return BudgetStatus.WARNING
        else:
            return BudgetStatus.HEALTHY
    
    def _generate_recommendations(
        self,
        monthly_pct: float,
        daily_pct: float,
        monthly_status: BudgetStatus,
        daily_status: BudgetStatus
    ) -> List[str]:
        """Generate budget optimization recommendations."""
        recommendations = []
        
        if monthly_pct > 80:
            recommendations.append("Consider enabling semantic caching to reduce costs")
            recommendations.append("Review model selection policy - favor local models")
        
        if daily_pct > 80:
            recommendations.append("Enable response validation to prevent low-quality responses")
            recommendations.append("Consider downgrading to local models for non-critical tasks")
        
        if monthly_status == BudgetStatus.EXCEEDED:
            recommendations.append("Budget exceeded - immediate action required")
            recommendations.append("Block non-essential requests until next billing period")
        
        return recommendations
    
    async def _store_budget_config(self, config: BudgetConfig):
        """Store budget configuration in database."""
        async with self.session_factory() as session:
            query = text("""
                INSERT INTO budget_configs (
                    tenant_id, level, team_id, project_id,
                    monthly_limit_usd, daily_limit_usd,
                    warning_threshold_pct, critical_threshold_pct,
                    action_on_exceed, alert_emails, slack_webhook,
                    created_at, updated_at
                )
                VALUES (:tenant_id, :level, :team_id, :project_id,
                        :monthly_limit_usd, :daily_limit_usd,
                        :warning_threshold_pct, :critical_threshold_pct,
                        :action_on_exceed, :alert_emails, :slack_webhook,
                        :created_at, :updated_at)
                ON CONFLICT (tenant_id, level, team_id, project_id)
                DO UPDATE SET
                    monthly_limit_usd = EXCLUDED.monthly_limit_usd,
                    daily_limit_usd = EXCLUDED.daily_limit_usd,
                    warning_threshold_pct = EXCLUDED.warning_threshold_pct,
                    critical_threshold_pct = EXCLUDED.critical_threshold_pct,
                    action_on_exceed = EXCLUDED.action_on_exceed,
                    alert_emails = EXCLUDED.alert_emails,
                    slack_webhook = EXCLUDED.slack_webhook,
                    updated_at = EXCLUDED.updated_at
            """)
            
            await session.execute(query, {
                "tenant_id": config.tenant_id,
                "level": config.level.value,
                "team_id": config.team_id,
                "project_id": config.project_id,
                "monthly_limit_usd": config.monthly_limit_usd,
                "daily_limit_usd": config.daily_limit_usd,
                "warning_threshold_pct": config.warning_threshold_pct,
                "critical_threshold_pct": config.critical_threshold_pct,
                "action_on_exceed": config.action_on_exceed,
                "alert_emails": config.alert_emails,
                "slack_webhook": config.slack_webhook,
                "created_at": config.created_at,
                "updated_at": config.updated_at
            })
            await session.commit()
    
    async def _load_budget_configs(self):
        """Load budget configurations from database."""
        async with self.session_factory() as session:
            query = text("SELECT * FROM budget_configs")
            result = await session.execute(query)
            
            for row in result:
                config = BudgetConfig(
                    tenant_id=row.tenant_id,
                    level=BudgetLevel(row.level),
                    team_id=row.team_id,
                    project_id=row.project_id,
                    monthly_limit_usd=row.monthly_limit_usd,
                    daily_limit_usd=row.daily_limit_usd,
                    warning_threshold_pct=row.warning_threshold_pct,
                    critical_threshold_pct=row.critical_threshold_pct,
                    action_on_exceed=row.action_on_exceed,
                    alert_emails=row.alert_emails or [],
                    slack_webhook=row.slack_webhook,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                
                key = self._generate_budget_key(
                    config.tenant_id, config.level, config.team_id, config.project_id
                )
                self._budget_configs[key] = config
    
    async def _load_active_alerts(self):
        """Load active alerts from database."""
        async with self.session_factory() as session:
            query = text("""
                SELECT * FROM budget_alerts 
                WHERE resolved_at IS NULL
                ORDER BY triggered_at DESC
            """)
            result = await session.execute(query)
            
            for row in result:
                alert = BudgetAlert(
                    alert_id=row.alert_id,
                    tenant_id=row.tenant_id,
                    level=BudgetLevel(row.level),
                    team_id=row.team_id,
                    project_id=row.project_id,
                    alert_type=AlertType(row.alert_type),
                    current_spend_usd=row.current_spend_usd,
                    limit_usd=row.limit_usd,
                    threshold_pct=row.threshold_pct,
                    triggered_at=row.triggered_at,
                    resolved_at=row.resolved_at,
                    notification_sent=row.notification_sent
                )
                self._active_alerts[alert.alert_id] = alert
    
    async def _check_and_create_alerts(self, tenant_id: str):
        """Check budget status and create alerts if needed."""
        # This would check all budget levels for the tenant
        # and create alerts if thresholds are exceeded
        pass
    
    async def _update_alert(self, alert: BudgetAlert):
        """Update alert in database."""
        async with self.session_factory() as session:
            query = text("""
                UPDATE budget_alerts
                SET resolved_at = :resolved_at,
                    notification_sent = :notification_sent
                WHERE alert_id = :alert_id
            """)
            
            await session.execute(query, {
                "alert_id": alert.alert_id,
                "resolved_at": alert.resolved_at,
                "notification_sent": alert.notification_sent
            })
            await session.commit()
