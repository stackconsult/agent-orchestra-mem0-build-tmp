"""
Rules Context Source - Builds Rules Layer (Two-Wall System)

StackConsulting Pattern: Define hard and soft constraints that govern
agent behavior, compliance, and interaction patterns.
"""

from typing import Dict, Any, Optional, List

from ..models import RulesContext

logger = __import__("logging").getLogger(__name__)


def build_rules_context(tenant_policies: Optional[Dict[str, Any]] = None) -> RulesContext:
    """
    Build the Rules layer with hard and soft walls.
    
    Args:
        tenant_policies: Optional tenant-specific policy overrides
    
    Returns:
        RulesContext with soft and hard walls
    """
    # Default soft walls (advisory constraints)
    soft_walls = {
        # StackConsulting voice and style
        "brand_voice": "sharp, practical, operator-focused",
        "style": "short paragraphs, clear bullets, no fluff",
        "tone": "professional but approachable",
        
        # Communication preferences
        "include_next_steps": True,
        "prefer_actionable_insights": True,
        "use_concrete_examples": True,
        "avoid_jargon_unless_necessary": True,
        
        # Output formatting
        "default_format": "markdown",
        "include_code_blocks": True,
        "add_syntax_highlighting": True,
        
        # Best practices
        "consider_security_first": True,
        "think_about_scalability": True,
        "include_monitoring_suggestions": True,
        "document_assumptions": True,
    }
    
    # Default hard walls (mandatory constraints)
    hard_walls = {
        # Security and compliance
        "forbidden_actions": [
            "execute_live_code",
            "change_prod_config_without_approval",
            "access_sensitive_data_without_authorization",
            "bypass_security_controls",
        ],
        "pii_handling": "never log secrets, redact access tokens, mask personal data",
        "security_scan_required": True,
        
        # Validation requirements
        "schema_validation": True,
        "input_sanitization": True,
        "output_validation": True,
        
        # Operational constraints
        "max_response_time_seconds": 30,
        "max_tokens_per_response": 4000,
        "require_human_approval_for": [
            "destructive_operations",
            "production_changes",
            "security_policy_changes",
        ],
        
        # Data handling
        "encrypt_sensitive_data": True,
        "audit_log_access": True,
        "retention_policy_days": 90,
        
        # Model constraints
        "allowed_model_providers": ["anthropic", "openai", "ollama"],
        "forbidden_model_types": ["unvalidated_models"],
        "temperature_range": [0.0, 1.0],
    }
    
    # Default validation schemas
    validation_schemas = {
        "user_input": {
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string", "max_length": 10000},
                "task_type": {"type": "string"},
                "session_id": {"type": "string"},
            },
        },
        "agent_response": {
            "type": "object",
            "required": ["response"],
            "properties": {
                "response": {"type": "string", "max_length": 50000},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "requires_approval": {"type": "boolean"},
            },
        },
    }
    
    # Apply tenant-specific overrides if provided
    if tenant_policies:
        soft_walls.update(tenant_policies.get("soft_walls", {}))
        hard_walls.update(tenant_policies.get("hard_walls", {}))
        validation_schemas.update(tenant_policies.get("validation_schemas", {}))
    
    return RulesContext(
        soft_walls=soft_walls,
        hard_walls=hard_walls,
        tenant_policies=tenant_policies or {},
        validation_schemas=validation_schemas,
    )


def validate_against_rules(
    data: Dict[str, Any],
    rules_context: RulesContext,
    schema_name: Optional[str] = None
) -> tuple[bool, List[str]]:
    """
    Validate data against rules context.
    
    Args:
        data: Data to validate
        rules_context: Rules context with constraints
        schema_name: Optional specific schema to validate against
    
    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []
    
    # Check hard walls first (these must pass)
    for rule, value in rules_context.hard_walls.items():
        if rule == "forbidden_actions" and "action" in data:
            if data["action"] in value:
                violations.append(f"Forbidden action detected: {data['action']}")
        
        elif rule == "max_response_time_seconds" and "response_time" in data:
            if data["response_time"] > value:
                violations.append(f"Response time exceeds limit: {data['response_time']} > {value}")
        
        elif rule == "max_tokens_per_response" and "token_count" in data:
            if data["token_count"] > value:
                violations.append(f"Token count exceeds limit: {data['token_count']} > {value}")
    
    # Check validation schemas if specified
    if schema_name and schema_name in rules_context.validation_schemas:
        schema = rules_context.validation_schemas[schema_name]
        violations.extend(_validate_schema(data, schema))
    
    # Check soft walls (these are warnings, not failures)
    soft_violations = []
    for rule, value in rules_context.soft_walls.items():
        if rule == "include_next_steps" and value and "next_steps" not in data:
            soft_violations.append("Consider including next steps for better user experience")
        
        elif rule == "prefer_actionable_insights" and value and "actionable" not in data.get("response", "").lower():
            soft_violations.append("Response should include actionable insights")
    
    # Log soft violations but don't fail validation
    if soft_violations:
        logger.info(f"Soft wall violations: {soft_violations}")
    
    return len(violations) == 0, violations


def _validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """
    Simple schema validation - in production, use a proper validator like jsonschema.
    """
    violations = []
    
    # Check required fields
    if "required" in schema:
        for field in schema["required"]:
            if field not in data:
                violations.append(f"Required field missing: {field}")
    
    # Check field types and constraints
    if "properties" in schema:
        for field, field_schema in schema["properties"].items():
            if field in data:
                value = data[field]
                
                # Type checking
                if "type" in field_schema:
                    expected_type = field_schema["type"]
                    if expected_type == "string" and not isinstance(value, str):
                        violations.append(f"Field {field} must be a string")
                    elif expected_type == "number" and not isinstance(value, (int, float)):
                        violations.append(f"Field {field} must be a number")
                    elif expected_type == "boolean" and not isinstance(value, bool):
                        violations.append(f"Field {field} must be a boolean")
                
                # Length checking
                if "max_length" in field_schema and isinstance(value, str):
                    if len(value) > field_schema["max_length"]:
                        violations.append(f"Field {field} exceeds max length")
                
                # Range checking
                if "minimum" in field_schema and isinstance(value, (int, float)):
                    if value < field_schema["minimum"]:
                        violations.append(f"Field {field} below minimum value")
                
                if "maximum" in field_schema and isinstance(value, (int, float)):
                    if value > field_schema["maximum"]:
                        violations.append(f"Field {field} exceeds maximum value")
    
    return violations


def get_compliance_checks(rules_context: RulesContext) -> List[Dict[str, Any]]:
    """
    Get compliance checks based on rules context.
    
    Returns:
        List of compliance check configurations
    """
    checks = []
    
    # Security checks
    if rules_context.hard_walls.get("security_scan_required"):
        checks.append({
            "type": "security_scan",
            "severity": "high",
            "description": "Scan for security vulnerabilities",
        })
    
    # PII checks
    if "pii_handling" in rules_context.hard_walls:
        checks.append({
            "type": "pii_detection",
            "severity": "high",
            "description": "Detect and redact PII data",
        })
    
    # Schema validation
    if rules_context.hard_walls.get("schema_validation"):
        checks.append({
            "type": "schema_validation",
            "severity": "medium",
            "description": "Validate against defined schemas",
        })
    
    # Approval checks
    if "require_human_approval_for" in rules_context.hard_walls:
        for action in rules_context.hard_walls["require_human_approval_for"]:
            checks.append({
                "type": "approval_required",
                "severity": "high",
                "action": action,
                "description": f"Human approval required for {action}",
            })
    
    return checks
