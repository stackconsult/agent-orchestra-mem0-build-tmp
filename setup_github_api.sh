#!/bin/bash

# GitHub REST API Setup Script
# This script sets up the environment for GitHub REST API usage

echo "🚀 GitHub REST API Setup Script"
echo "================================"

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI is not installed. Installing..."
    brew install gh
else
    echo "✅ GitHub CLI is already installed: $(gh --version)"
fi

# Create API documentation directory
echo "📁 Creating API documentation directory..."
mkdir -p docs/api

# Download official GitHub REST API documentation
echo "📥 Downloading official GitHub REST API documentation..."
curl -o docs/api/GITHUB_REST_API_OFFICIAL.html "https://docs.github.com/en/rest/using-the-rest-api/getting-started-with-the-rest-api?apiVersion=2022-11-28&tool=curl"

# Create a quick reference file
echo "📝 Creating quick reference file..."
cat > docs/api/QUICK_REFERENCE.md << 'EOF'
# GitHub REST API Quick Reference

## Base URL
```
https://api.github.com
```

## Required Headers
```bash
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
Authorization: Bearer YOUR_TOKEN
User-Agent: YOUR_APP_NAME
```

## Basic curl Template
```bash
curl --request METHOD \
     --url "https://api.github.com/PATH" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: YOUR_APP_NAME"
```

## Common Endpoints
```bash
# Get user info
GET /user

# List repositories
GET /user/repos

# Get repository
GET /repos/{owner}/{repo}

# List issues
GET /repos/{owner}/{repo}/issues

# Create issue
POST /repos/{owner}/{repo}/issues
```

## Authentication Setup
```bash
# Authenticate with GitHub CLI
gh auth login

# Create personal access token
gh auth token

# Test authentication
gh api user
```

## Rate Limits
- Unauthenticated: 60 requests/hour
- Authenticated: 5000 requests/hour

Check rate limits:
```bash
gh api rate_limit
```
EOF

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run: gh auth login"
echo "2. Check documentation in: docs/api/"
echo "3. Test with: gh api user"
echo ""
echo "📚 Documentation files created:"
echo "  - docs/api/GITHUB_REST_API_OFFICIAL.html (official docs)"
echo "  - docs/api/GITHUB_REST_API_DOCUMENTATION.md (organized docs)"
echo "  - docs/api/QUICK_REFERENCE.md (quick reference)"
