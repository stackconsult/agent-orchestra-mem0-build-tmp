"""
User Profile Context Source - Builds User Layer

StackConsulting Pattern: Extract user identity, preferences, and history
from auth claims and mem0 memory system.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..models import UserContext

logger = __import__("logging").getLogger(__name__)


def build_user_context(auth_claims: Dict[str, Any], mem0_client=None) -> UserContext:
    """
    Build the User layer from authentication claims and memory system.
    
    Args:
        auth_claims: Authentication data from JWT/middleware
        mem0_client: Optional mem0 client for user history
    
    Returns:
        UserContext with user information and preferences
    """
    # Extract basic user info from auth
    user_id = auth_claims.get("sub") or auth_claims.get("user_id")
    tenant_id = auth_claims.get("tenant_id") or auth_claims.get("organization_id")
    roles = auth_claims.get("roles", auth_claims.get("groups", []))
    
    # Default preferences based on role and expertise
    preferences = {
        "tone": "professional",
        "detail_level": "medium",
        "format": "markdown",
        "include_examples": True,
        "language": "english",
    }
    
    # Adjust preferences based on roles
    if "admin" in roles or "developer" in roles:
        preferences.update({
            "tone": "technical",
            "detail_level": "high",
            "include_code": True,
        })
    elif "executive" in roles or "manager" in roles:
        preferences.update({
            "tone": "executive",
            "detail_level": "summary",
            "include_metrics": True,
        })
    
    # Determine expertise level
    expertise_level = "intermediate"
    if "senior" in roles or "lead" in roles:
        expertise_level = "expert"
    elif "junior" in roles or "intern" in roles:
        expertise_level = "beginner"
    
    # Get history from mem0 if available
    history_summary = None
    session_count = None
    last_seen = None
    
    if mem0_client and user_id:
        try:
            # Fetch user summary from mem0
            history_data = mem0_client.get_user_summary(user_id=user_id)
            if history_data:
                history_summary = history_data.get("summary", "No previous history")
                session_count = history_data.get("session_count", 0)
                last_seen = history_data.get("last_seen")
        except Exception as e:
            logger.warning(f"Failed to fetch user history from mem0: {e}")
    
    # Apply explicit preferences from auth claims if present
    if "preferences" in auth_claims:
        preferences.update(auth_claims["preferences"])
    
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        expertise_level=expertise_level,
        preferences=preferences,
        history_summary=history_summary,
        session_count=session_count,
        last_seen=last_seen or datetime.utcnow(),
    )


def enrich_user_context(user_context: UserContext, interaction_data: Dict[str, Any]) -> UserContext:
    """
    Enrich user context with interaction data (e.g., from current session).
    
    Args:
        user_context: Existing user context
        interaction_data: Data from current interaction
    
    Returns:
        Enriched UserContext
    """
    # Update preferences based on interaction patterns
    if interaction_data.get("asked_for_code"):
        user_context.preferences["include_code"] = True
    
    if interaction_data.get("preferred_brief"):
        user_context.preferences["detail_level"] = "low"
    
    if interaction_data.get("asked_for_details"):
        user_context.preferences["detail_level"] = "high"
    
    # Update expertise based on question complexity
    if interaction_data.get("asked_advanced_questions"):
        if user_context.expertise_level == "beginner":
            user_context.expertise_level = "intermediate"
        elif user_context.expertise_level == "intermediate":
            user_context.expertise_level = "expert"
    
    return user_context
