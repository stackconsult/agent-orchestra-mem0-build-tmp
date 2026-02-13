"""
Security Tests for Context Engineering

Tests to verify that the security fixes for CodeQL vulnerabilities are working correctly.
"""

import pytest
import os
import tempfile
from unittest.mock import patch

from context_engineering.sources.domain_graph import validate_repo_path, build_domain_context
from config.security_config import validate_repo_path_security, sanitize_error_message, is_safe_file


class TestPathTraversalProtection:
    """Test path traversal protection in domain_graph.py"""
    
    def test_validate_repo_path_blocks_traversal(self):
        """Test that path traversal attempts are blocked"""
        # Test various path traversal attempts
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "repo/../../../secret",
            "normal/../dangerous",
        ]
        
        for path in dangerous_paths:
            result = validate_repo_path(path)
            assert result is None, f"Path traversal not blocked: {path}"
    
    def test_validate_repo_path_allows_safe_paths(self):
        """Test that safe paths are allowed"""
        safe_paths = [
            "my-repo",
            "project/subdir",
            "user-repo-123",
            "test_project",
        ]
        
        with patch.dict(os.environ, {"ALLOWED_REPO_BASE_DIR": "/tmp/test"}):
            os.makedirs("/tmp/test", exist_ok=True)
            
            for path in safe_paths:
                result = validate_repo_path(path)
                assert result is not None, f"Safe path blocked: {path}"
                assert "/tmp/test" in result, f"Path not in base directory: {result}"
    
    def test_validate_repo_path_security_config(self):
        """Test security configuration validation"""
        # Valid path
        result = validate_repo_path_security("my-repo")
        assert result["valid"] is True
        assert result["reason"] is None
        
        # Invalid path (traversal)
        result = validate_repo_path_security("../etc/passwd")
        assert result["valid"] is False
        assert "Path traversal" in result["reason"]
        
        # Invalid path (too long)
        long_path = "a" * 300
        result = validate_repo_path_security(long_path)
        assert result["valid"] is False
        assert "too long" in result["reason"]


class TestInformationExposureProtection:
    """Test information exposure protection in security_headers.py"""
    
    def test_sanitize_error_message_removes_secrets(self):
        """Test that sensitive information is removed from error messages"""
        sensitive_messages = [
            "Database password: secret123",
            "JWT token: abc.def.ghi",
            "API key is sk-1234567890",
            "Private key: -----BEGIN RSA-----",
            "Credential file at /home/user/.aws/credentials",
        ]
        
        for message in sensitive_messages:
            sanitized = sanitize_error_message(message)
            assert sanitized == "Internal server error", f"Sensitive info not removed: {message}"
    
    def test_sanitize_error_message_allows_safe(self):
        """Test that safe error messages are preserved"""
        safe_messages = [
            "File not found",
            "Invalid input format",
            "Connection timeout",
            "Permission denied to resource",
        ]
        
        with patch.dict(os.environ, {"SANITIZE_ERROR_MESSAGES": "false"}):
            for message in safe_messages:
                sanitized = sanitize_error_message(message)
                assert sanitized == message, f"Safe message changed: {message}"
    
    def test_sanitize_error_message_blocks_paths(self):
        """Test that file paths are removed from error messages"""
        path_messages = [
            "Error at /home/user/project/app.py:123",
            "File C:\\Windows\\system32\\config not accessible",
            "Traceback: File '/var/log/app.log', line 45",
        ]
        
        for message in path_messages:
            sanitized = sanitize_error_message(message)
            assert sanitized == "Internal server error", f"Path not removed: {message}"


class TestFileSafetyChecks:
    """Test file safety validation"""
    
    def test_is_safe_file_blocks_dangerous(self):
        """Test that dangerous files are blocked"""
        dangerous_files = [
            ".env",
            ".env.production",
            "id_rsa",
            "private.key",
            "config/secrets.json",
            ".git/config",
            "__pycache__/app.pyc",
            "node_modules/package.json",
            "database.sql",
            "error.log",
        ]
        
        for file_path in dangerous_files:
            assert not is_safe_file(file_path), f"Dangerous file allowed: {file_path}"
    
    def test_is_safe_file_allows_safe(self):
        """Test that safe files are allowed"""
        safe_files = [
            "app.py",
            "package.json",
            "README.md",
            "Dockerfile",
            "requirements.txt",
            "config.yaml",
            "src/main.tsx",
            "tests/test_app.py",
            "docs/api.md",
        ]
        
        for file_path in safe_files:
            assert is_safe_file(file_path), f"Safe file blocked: {file_path}"


class TestDomainContextSecurity:
    """Test security in domain context building"""
    
    def test_build_domain_context_with_malicious_path(self):
        """Test that malicious paths are handled safely"""
        malicious_context = {
            "repository_path": "../../../etc/passwd",
            "project_id": "test-project"
        }
        
        # Should not crash and should handle malicious path safely
        domain = build_domain_context(malicious_context)
        
        # Should have safe default values
        assert domain.repo_summary == "Invalid repository path"
        assert domain.key_components == {}
    
    def test_build_domain_context_with_safe_path(self):
        """Test that safe paths work correctly"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a safe repository structure
            repo_path = os.path.join(temp_dir, "test-repo")
            os.makedirs(repo_path)
            
            # Create safe files
            with open(os.path.join(repo_path, "README.md"), "w") as f:
                f.write("# Test Repository")
            
            with open(os.path.join(repo_path, "package.json"), "w") as f:
                f.write('{"name": "test"}')
            
            safe_context = {
                "repository_path": "test-repo",
                "project_id": "test-project"
            }
            
            with patch.dict(os.environ, {"ALLOWED_REPO_BASE_DIR": temp_dir}):
                domain = build_domain_context(safe_context)
                
                # Should successfully analyze
                assert "documentation" in domain.related_docs
                assert "frontend" in domain.key_components


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
