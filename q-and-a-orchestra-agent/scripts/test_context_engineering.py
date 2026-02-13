#!/usr/bin/env python3
"""
Test Context Engineering Integration

This script tests the 6-Layer Context Engineering system end-to-end.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context_engineering import (
    build_context_envelope,
    ContextConfig,
    ContextOverride,
    apply_token_budget,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockMem0Client:
    """Mock mem0 client for testing."""
    
    async def get_user_summary(self, user_id: str) -> Dict[str, Any]:
        """Return mock user summary."""
        return {
            "summary": "User has worked on 5 projects, prefers TypeScript, and has been active for 3 months",
            "session_count": 42,
            "last_seen": datetime.utcnow().isoformat(),
        }


class MockRepoAnalyzer:
    """Mock repository analyzer for testing."""
    
    async def get_repo_summary(self, repo_path: str) -> Dict[str, Any]:
        """Return mock repository analysis."""
        return {
            "summary": f"Repository at {repo_path} is a FastAPI-based microservice with PostgreSQL database",
            "components": {
                "api": "FastAPI REST API",
                "database": "PostgreSQL with pgvector",
                "auth": "JWT-based authentication",
                "frontend": "React TypeScript application",
            },
            "related_docs": {
                "README.md": "Project documentation",
                "api/docs": "OpenAPI specification",
            },
        }


async def test_basic_context_building():
    """Test basic context building functionality."""
    print("\n=== Testing Basic Context Building ===")
    
    # Mock auth claims
    auth_claims = {
        "sub": "test-user-123",
        "tenant_id": "test-tenant",
        "roles": ["developer", "admin"],
        "preferences": {
            "tone": "technical",
            "detail_level": "high",
        },
    }
    
    # Mock request body
    request_body = {
        "message": "I need to analyze my repository for security vulnerabilities",
        "task_type": "security_analysis",
        "repository_path": "/tmp/test-repo",
        "project_id": "project-456",
    }
    
    # Build context envelope
    envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body=request_body,
        mem0_client=MockMem0Client(),
        repo_analyzer_client=MockRepoAnalyzer(),
    )
    
    # Verify envelope structure
    assert envelope.context_id is not None
    assert envelope.user.user_id == "test-user-123"
    assert envelope.intent.primary_intent == "security_analysis"
    assert envelope.domain.repo_path == "/tmp/test-repo"
    assert envelope.rules.hard_walls is not None
    assert envelope.environment.environment is not None
    assert envelope.exposition.narrative is not None
    
    print(f"✅ Context envelope built successfully")
    print(f"   Context ID: {envelope.context_id}")
    print(f"   Primary Intent: {envelope.intent.primary_intent}")
    print(f"   Token Count: {envelope.token_budget_used}")
    print(f"   Processing Time: {envelope.processing_time_ms:.2f}ms")
    
    return envelope


async def test_context_overrides():
    """Test context override functionality."""
    print("\n=== Testing Context Overrides ===")
    
    auth_claims = {
        "sub": "test-user-456",
        "tenant_id": "test-tenant",
        "roles": ["user"],
    }
    
    request_body = {
        "message": "Help me understand this codebase",
        "task_type": "repo_analysis",
    }
    
    # Apply overrides
    overrides = ContextOverride(
        override_user_preferences={"detail_level": "expert"},
        override_intent={"primary_intent": "architecture_design"},
        override_rules={"hard_walls": {"allow_live_exec": True}},
    )
    
    envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body=request_body,
        mem0_client=MockMem0Client(),
        repo_analyzer_client=MockRepoAnalyzer(),
        override=overrides,
    )
    
    # Verify overrides were applied
    assert envelope.user.preferences.get("detail_level") == "expert"
    assert envelope.intent.primary_intent == "architecture_design"
    assert envelope.rules.hard_walls.get("allow_live_exec") is True
    
    print(f"✅ Context overrides applied successfully")
    print(f"   Override Intent: {envelope.intent.primary_intent}")
    print(f"   Override Detail Level: {envelope.user.preferences['detail_level']}")
    
    return envelope


async def test_token_budget():
    """Test token budget enforcement."""
    print("\n=== Testing Token Budget ===")
    
    # Build a large context
    auth_claims = {
        "sub": "test-user-789",
        "tenant_id": "test-tenant",
        "roles": ["developer"] * 100,  # Inflate roles
        "preferences": {f"pref_{i}": f"value_{i}" for i in range(100)},  # Inflate preferences
    }
    
    request_body = {
        "message": "A" * 10000,  # Long message
        "task_type": "architecture_design",
        "repository_path": "/tmp/very-large-repo",
    }
    
    envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body=request_body,
        mem0_client=MockMem0Client(),
        repo_analyzer_client=MockRepoAnalyzer(),
    )
    
    original_tokens = envelope.token_budget_used
    print(f"   Original token count: {original_tokens}")
    
    # Apply token budget
    budgeted_envelope = apply_token_budget(envelope, max_tokens=2000)
    
    print(f"   Budgeted token count: {budgeted_envelope.token_budget_used}")
    assert budgeted_envelope.token_budget_used <= 2000
    
    print(f"✅ Token budget enforcement working")
    
    return budgeted_envelope


async def test_intent_detection():
    """Test intent detection accuracy."""
    print("\n=== Testing Intent Detection ===")
    
    test_cases = [
        {
            "message": "I need to design a microservices architecture",
            "expected_intent": "architecture_design",
        },
        {
            "message": "There's a bug in my authentication system",
            "expected_intent": "troubleshooting",
        },
        {
            "message": "Implement a new user registration endpoint",
            "expected_intent": "implementation",
        },
        {
            "message": "Check for security vulnerabilities in my code",
            "expected_intent": "security_analysis",
        },
        {
            "message": "My application is running slow",
            "expected_intent": "performance_optimization",
        },
    ]
    
    auth_claims = {"sub": "test-user", "tenant_id": "test-tenant"}
    
    for i, case in enumerate(test_cases):
        request_body = {
            "message": case["message"],
            "task_type": None,  # Let it detect from message
        }
        
        envelope = await build_context_envelope(
            auth_claims=auth_claims,
            request_body=request_body,
        )
        
        detected = envelope.intent.primary_intent
        expected = case["expected_intent"]
        
        if detected == expected:
            print(f"   ✅ Test {i+1}: '{case['message'][:30]}...' -> {detected}")
        else:
            print(f"   ❌ Test {i+1}: '{case['message'][:30]}...' -> {detected} (expected {expected})")
    
    print(f"✅ Intent detection tests completed")


async def test_compliance_rules():
    """Test compliance rule enforcement."""
    print("\n=== Testing Compliance Rules ===")
    
    auth_claims = {
        "sub": "test-user",
        "tenant_id": "compliant-tenant",
        "roles": ["developer"],
    }
    
    request_body = {
        "message": "Execute this code in production",
        "task_type": "implementation",
    }
    
    # Add tenant policies with strict compliance
    tenant_policies = {
        "hard_walls": {
            "forbidden_actions": ["execute_live_code", "change_prod_config"],
            "compliance_level": "SOC2",
            "require_approval": True,
        },
        "soft_walls": {
            "tone": "formal",
            "include_disclaimer": True,
        },
    }
    
    envelope = await build_context_envelope(
        auth_claims=auth_claims,
        request_body=request_body,
        tenant_policies=tenant_policies,
    )
    
    # Verify rules were applied
    assert "execute_live_code" in envelope.rules.hard_walls["forbidden_actions"]
    assert envelope.rules.hard_walls["compliance_level"] == "SOC2"
    assert envelope.rules.soft_walls["tone"] == "formal"
    
    print(f"✅ Compliance rules applied successfully")
    print(f"   Forbidden Actions: {envelope.rules.hard_walls['forbidden_actions']}")
    print(f"   Compliance Level: {envelope.rules.hard_walls['compliance_level']}")
    
    return envelope


async def test_performance():
    """Test context building performance."""
    print("\n=== Testing Performance ===")
    
    auth_claims = {
        "sub": "perf-test-user",
        "tenant_id": "perf-tenant",
        "roles": ["developer"],
    }
    
    request_body = {
        "message": "Analyze my repository for improvements",
        "task_type": "repo_analysis",
        "repository_path": "/tmp/test-repo",
    }
    
    # Run multiple iterations
    iterations = 10
    times = []
    
    for i in range(iterations):
        start = datetime.utcnow()
        
        envelope = await build_context_envelope(
            auth_claims=auth_claims,
            request_body=request_body,
            mem0_client=MockMem0Client(),
            repo_analyzer_client=MockRepoAnalyzer(),
        )
        
        end = datetime.utcnow()
        times.append((end - start).total_seconds() * 1000)
    
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"   Iterations: {iterations}")
    print(f"   Average Time: {avg_time:.2f}ms")
    print(f"   Min Time: {min_time:.2f}ms")
    print(f"   Max Time: {max_time:.2f}ms")
    
    # Performance assertion - should be under 100ms on average
    assert avg_time < 100, f"Average time {avg_time}ms exceeds 100ms threshold"
    
    print(f"✅ Performance test passed")


async def main():
    """Run all context engineering tests."""
    print("🚀 Starting Context Engineering Tests")
    print("=" * 50)
    
    try:
        # Run all tests
        await test_basic_context_building()
        await test_context_overrides()
        await test_token_budget()
        await test_intent_detection()
        await test_compliance_rules()
        await test_performance()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed successfully!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
