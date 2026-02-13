#!/bin/bash
# Security Verification Checklist
# Run this script to verify all security fixes are properly implemented

set -e

echo "=== 🔒 Security Verification Checklist ==="
echo ""

FAILED_CHECKS=0
TOTAL_CHECKS=0

# Helper function to run a check
run_check() {
    local check_name="$1"
    local check_command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -n "[$TOTAL_CHECKS] $check_name... "
    
    if eval "$check_command" >/dev/null 2>&1; then
        echo "✅ PASS"
        return 0
    else
        echo "❌ FAIL"
        echo "   Command: $check_command"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# 1. CORS Check
echo "🔍 Checking CORS configuration..."
run_check "No wildcard CORS origins" \
    "! grep -r 'allow_origins=\[\"\*\"\]' . --exclude-dir=__pycache__ --exclude='*test*' --exclude='tests/*'"

run_check "CORS config file exists" \
    "test -f config/cors_config.py"

run_check "Environment-based CORS implemented" \
    "grep -q 'get_cors_config()' main*.py"

# 2. Hardcoded Passwords Check
echo ""
echo "🔍 Checking for hardcoded passwords..."
run_check "No hardcoded passwords in docker-compose" \
    "! grep -E 'POSTGRES_PASSWORD.*password|REDIS_PASSWORD.*redis|GF_SECURITY_ADMIN_PASSWORD.*admin' docker-compose*.yml"

run_check "No hardcoded passwords in config files" \
    "! grep -E 'password.*=' deployment/kubernetes/configmap.yaml | grep -v 'env_file\|getenv\|\$'"

run_check "Secure startup script exists" \
    "test -f scripts/start_dev.sh"

# 3. Secrets in Git Check
echo ""
echo "🔍 Checking for secrets in git..."
run_check "No base64 secrets in git" \
    "! grep -r 'BEGIN RSA PRIVATE KEY\|BEGIN PRIVATE KEY\|sk-ant-\|sk-\|ghp_' deployment/kubernetes/secrets.yaml | grep -v 'valueFrom\|<.*>'"

run_check "Secrets use stringData instead of data" \
    "grep -q 'stringData:' deployment/kubernetes/secrets.yaml"

# 4. .env.example Check
echo ""
echo "🔍 Checking .env.example..."
run_check "No real credentials in .env.example" \
    "! grep -E '(sk-ant-[a-zA-Z0-9]{40,}|sk-[a-zA-Z0-9]{48,}|ghp_[a-zA-Z0-9]{36,}|password=[a-zA-Z0-9]{8,})' .env.example"

run_check "Placeholders used instead of real values" \
    "grep -q '<your-actual-key-here>' .env.example"

# 5. Input Validation Check
echo ""
echo "🔍 Checking input validation..."
run_check "Pydantic validation schemas exist" \
    "test -f schemas/request_validation.py"

run_check "Input validation models present" \
    "grep -q 'class.*Request.*BaseModel' schemas/request_validation.py"

run_check "Content sanitization implemented" \
    "grep -q 'sanitize_content\|validate_no_injection' schemas/request_validation.py"

# 6. Rate Limiting Check
echo ""
echo "🔍 Checking rate limiting..."
run_check "Rate limiting middleware exists" \
    "test -f middleware/rate_limiting.py"

run_check "Rate limiting applied to main app" \
    "grep -q 'RateLimitMiddleware' main_v2.py"

run_check "Rate limits configured for endpoints" \
    "grep -q 'endpoint_limits\|invoke.*10' middleware/rate_limiting.py"

# 7. Security Headers Check
echo ""
echo "🔍 Checking security headers..."
run_check "Security headers middleware exists" \
    "test -f middleware/security_headers.py"

run_check "CSP headers implemented" \
    "grep -q 'Content-Security-Policy' middleware/security_headers.py"

run_check "HSTS headers configured" \
    "grep -q 'Strict-Transport-Security' middleware/security_headers.py"

run_check "Security headers applied to main app" \
    "grep -q 'SecurityHeadersMiddleware' main_v2.py"

# 8. Error Handling Check
echo ""
echo "🔍 Checking error handling..."
run_check "Error sanitization middleware exists" \
    "grep -q 'ErrorHandlingMiddleware' middleware/security_headers.py"

run_check "Production error hiding implemented" \
    "grep -q 'env.*==.*production' middleware/security_headers.py"

# 9. Prompt Injection Check
echo ""
echo "🔍 Checking prompt injection detection..."
run_check "Prompt injection detector exists" \
    "test -f security/prompt_injection_detector.py"

run_check "Injection patterns defined" \
    "grep -q 'INJECTION_PATTERNS' security/prompt_injection_detector.py"

run_check "Detection confidence threshold set" \
    "grep -q 'threshold.*=' security/prompt_injection_detector.py"

# 10. CI/CD Security Check
echo ""
echo "🔍 Checking CI/CD security..."
run_check "Security workflow exists" \
    "test -f ../.github/workflows/security.yml"

run_check "Secret scanning in CI/CD" \
    "grep -q 'trufflehog\|detect-secrets' ../.github/workflows/security.yml"

run_check "SAST scanning configured" \
    "grep -q 'bandit\|semgrep' ../.github/workflows/security.yml"

run_check "Container scanning enabled" \
    "grep -q 'trivy' ../.github/workflows/security.yml"

# 11. Additional Security Checks
echo ""
echo "🔍 Checking additional security measures..."
run_check "Request size limiting implemented" \
    "grep -q 'RequestSizeLimitMiddleware' middleware/security_headers.py"

run_check "Tenant isolation middleware present" \
    "grep -q 'tenant_middleware\|MultiTenancyManager' main_v2.py"

run_check "Audit logging configured" \
    "grep -q 'AuditLogger\|audit_logging' main_v2.py"

# Summary
echo ""
echo "=== 📊 VERIFICATION SUMMARY ==="
echo "Total checks: $TOTAL_CHECKS"
echo "Passed: $((TOTAL_CHECKS - FAILED_CHECKS))"
echo "Failed: $FAILED_CHECKS"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo ""
    echo "🎉 ALL SECURITY CHECKS PASSED!"
    echo "✅ Repository is ready for production deployment"
    exit 0
else
    echo ""
    echo "⚠️  SECURITY ISSUES FOUND"
    echo "❌ Please address the failed checks before production deployment"
    echo ""
    echo "📋 Failed checks summary:"
    echo "   - Review the ❌ FAIL messages above"
    echo "   - Fix each issue and re-run this script"
    echo "   - Refer to SECURITY_HARDENING_CHECKLIST.md for guidance"
    exit 1
fi
