#!/usr/bin/env python3
"""
Agent Orchestra Context Engineering Preview

This demo shows the 6-Layer Context Engineering in action
without requiring heavy dependencies or external services.
"""

import json
import sys
import os
from datetime import datetime

# Add the context engineering module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'q-and-a-orchestra-agent'))

def demo_context_engineering():
    """Demonstrate the 6-Layer Context Engineering framework."""
    
    print("🚀 Agent Orchestra with 6-Layer Context Engineering")
    print("=" * 60)
    print()
    
    # Simulate a user request
    user_request = {
        "messages": [{"role": "user", "content": "Help me implement user authentication in my FastAPI app"}],
        "task_type": "implementation",
        "repository_path": "demo-project",
        "user_id": "user-123",
        "tenant_id": "acme-corp"
    }
    
    print("📝 User Request:")
    print(f"   Content: {user_request['messages'][0]['content']}")
    print(f"   Task Type: {user_request['task_type']}")
    print()
    
    # Demonstrate the 6 layers
    print("🔍 Building 6-Layer Context...")
    print()
    
    # Layer 1: User Context
    user_context = {
        "user_id": user_request["user_id"],
        "tenant_id": user_request["tenant_id"],
        "expertise_level": "intermediate",
        "preferences": {
            "tone": "professional",
            "detail_level": "comprehensive",
            "include_examples": True
        },
        "history": ["previous_auth_questions", "fastapi_tutorial_completed"]
    }
    
    print("👤 Layer 1 - User Context:")
    print(f"   Expertise: {user_context['expertise_level']}")
    print(f"   Preferences: {user_context['preferences']}")
    print(f"   History: {len(user_context['history'])} previous interactions")
    print()
    
    # Layer 2: Intent Detection
    intent_context = {
        "primary_intent": "implementation",
        "confidence": 0.95,
        "success_criteria": ["secure_auth", "working_code", "best_practices"],
        "constraints": ["no_external_deps", "fastapi_native", "production_ready"],
        "escalation_path": ["security_review", "code_review"]
    }
    
    print("🎯 Layer 2 - Intent Context:")
    print(f"   Intent: {intent_context['primary_intent']} (confidence: {intent_context['confidence']})")
    print(f"   Success Criteria: {intent_context['success_criteria']}")
    print(f"   Constraints: {intent_context['constraints']}")
    print()
    
    # Layer 3: Domain Context
    domain_context = {
        "repository_path": user_request["repository_path"],
        "project_type": "FastAPI Web Application",
        "key_components": {
            "backend": "Python/FastAPI",
            "database": "PostgreSQL",
            "authentication": "JWT-based"
        },
        "existing_patterns": ["rest_api", "middleware", "dependency_injection"],
        "related_docs": ["README.md", "docs/api.md"]
    }
    
    print("🏗️ Layer 3 - Domain Context:")
    print(f"   Project Type: {domain_context['project_type']}")
    print(f"   Components: {list(domain_context['key_components'].keys())}")
    print(f"   Existing Patterns: {domain_context['existing_patterns']}")
    print()
    
    # Layer 4: Rules Context
    rules_context = {
        "hard_walls": {
            "forbidden_actions": ["hardcoded_secrets", "plain_text_passwords"],
            "required_approvals": ["security_review"],
            "compliance": ["OWASP", "SOC2"]
        },
        "soft_walls": {
            "style": "PEP8_compliant",
            "documentation": "docstrings_required",
            "testing": "pytest_coverage_80%"
        }
    }
    
    print("⚖️ Layer 4 - Rules Context:")
    print(f"   Hard Walls: {list(rules_context['hard_walls'].keys())}")
    print(f"   Soft Walls: {list(rules_context['soft_walls'].keys())}")
    print()
    
    # Layer 5: Environment Context
    environment_context = {
        "deployment": "production",
        "system_load": "moderate",
        "feature_flags": {
            "advanced_security": True,
            "audit_logging": True
        },
        "rate_limits": {
            "api_calls": "1000/hour",
            "auth_attempts": "10/minute"
        }
    }
    
    print("🌍 Layer 5 - Environment Context:")
    print(f"   Deployment: {environment_context['deployment']}")
    print(f"   System Load: {environment_context['system_load']}")
    print(f"   Feature Flags: {list(environment_context['feature_flags'].keys())}")
    print()
    
    # Layer 6: Exposition Context (Fused Output)
    exposition_context = {
        "context_summary": "Intermediate developer implementing secure FastAPI authentication",
        "token_usage": {
            "total": 850,
            "by_layer": {"user": 120, "intent": 80, "domain": 200, "rules": 150, "environment": 100, "exposition": 200}
        },
        "routing_factors": {
            "model_selection": "gpt-4",
            "agent_flow": "implementation -> security_review -> code_generation",
            "priority": "high"
        }
    }
    
    print("🎨 Layer 6 - Exposition Context:")
    print(f"   Summary: {exposition_context['context_summary']}")
    print(f"   Token Usage: {exposition_context['token_usage']['total']} total")
    print(f"   Routing: {exposition_context['routing_factors']['agent_flow']}")
    print()
    
    # Show the intelligent routing decision
    print("🧠 Intelligent Routing Decision:")
    print(f"   Selected Model: {exposition_context['routing_factors']['model_selection']}")
    print(f"   Agent Flow: {exposition_context['routing_factors']['agent_flow']}")
    print(f"   Priority: {exposition_context['routing_factors']['priority']}")
    print()
    
    # Show what the AI agent receives
    print("📦 What the AI Agent Receives:")
    print("   === CONTEXT ENVELOPE ===")
    print(f"   User: Intermediate developer, prefers comprehensive examples")
    print(f"   Intent: Implement secure authentication (95% confidence)")
    print(f"   Domain: FastAPI app with PostgreSQL, existing REST patterns")
    print(f"   Rules: OWASP compliance required, PEP8 style preferred")
    print(f"   Environment: Production deployment with security features")
    print(f"   Exposition: Optimized for implementation task")
    print("   =========================")
    print()
    
    # Show the expected response
    print("💬 Expected AI Response:")
    print("   'I'll help you implement secure JWT authentication for your FastAPI app.")
    print("   'Based on your intermediate expertise, I'll provide a comprehensive solution")
    print("   'with proper security practices, following OWASP guidelines and PEP8 style.'")
    print()
    
    print("✨ Key Benefits Demonstrated:")
    print("   ✅ Zero prompt engineering - context built automatically")
    print("   ✅ Personalized response based on user expertise")
    print("   ✅ Compliance enforced by default (OWASP, SOC2)")
    print("   ✅ Domain-aware (knows it's a FastAPI project)")
    print("   ✅ Intelligent routing to optimal model/agent")
    print("   ✅ Production-ready with security considerations")
    print()
    
    print("🚀 This is the power of 6-Layer Context Engineering!")
    print("   Transform your AI systems from prompt-dependent to context-aware.")

def demo_security_features():
    """Demonstrate the security features."""
    
    print("\n🔒 Security Features Demo")
    print("=" * 40)
    
    # Path traversal protection
    dangerous_paths = ["../../../etc/passwd", "/root/.ssh", "..\\windows\\system32"]
    safe_paths = ["my-project", "user-repo", "app-source"]
    
    print("\n🛡️ Path Traversal Protection:")
    for path in dangerous_paths:
        print(f"   ❌ BLOCKED: {path}")
    for path in safe_paths:
        print(f"   ✅ ALLOWED: {path}")
    
    # Information exposure
    print("\n🔇 Information Exposure Prevention:")
    sensitive_errors = [
        "Database password: secret123",
        "API key: sk-1234567890",
        "File at /home/user/config.json"
    ]
    for error in sensitive_errors:
        print(f"   🚫 SANITIZED: '{error}' → 'Internal server error'")
    
    # Compliance enforcement
    print("\n⚖️ Compliance Enforcement:")
    print("   ✅ Hard Walls: Never break (security, compliance)")
    print("   📝 Soft Walls: Advisory (style, preferences)")
    print("   🔍 Automatic validation before model invocation")

if __name__ == "__main__":
    try:
        demo_context_engineering()
        demo_security_features()
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("📚 Learn more: CONTEXT_ENGINEERING.md")
        print("🚀 Get started: MIGRATION_TO_CONTEXT_ENGINEERING.md")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("This is a simplified demo - full version requires dependencies.")
