#!/bin/bash

# GitHub REST API Test Script
# Tests various GitHub API endpoints

echo "🧪 GitHub REST API Test Script"
echo "=============================="

# Check if authenticated
echo "🔐 Checking authentication status..."
if gh auth status &> /dev/null; then
    echo "✅ Authenticated with GitHub"
else
    echo "❌ Not authenticated. Please run 'gh auth login' first."
    exit 1
fi

# Test basic API calls
echo ""
echo "📡 Testing API endpoints..."

# Test user info
echo "1. Getting user information..."
gh api user --jq '.login, .name, .email'

# Test rate limits
echo ""
echo "2. Checking rate limits..."
gh api rate_limit --jq '.resources.core'

# Test repository list (limited)
echo ""
echo "3. Listing first 5 repositories..."
gh api user/repos --jq '.[:5] | .[] | {name: .name, private: .private, stars: .stargazers_count}'

# Test repository info
echo ""
echo "4. Getting repository info for this repo..."
if [ -d ".git" ]; then
    REPO_NAME=$(basename $(git rev-parse --show-toplevel))
    REPO_OWNER=$(git config --get remote.origin.url | sed -n 's/.*github.com[:/]\([^/]*\)\/.*/\1/p')
    if [ "$REPO_OWNER" != "" ] && [ "$REPO_NAME" != "" ]; then
        gh api repos/$REPO_OWNER/$REPO_NAME --jq '{name: .name, description: .description, stars: .stargazers_count, forks: .forks_count}'
    else
        echo "Could not determine repository info"
    fi
else
    echo "Not in a git repository"
fi

echo ""
echo "✅ API tests completed successfully!"
echo ""
echo "📊 Current API Usage:"
gh api rate_limit --jq '"Core: \(.resources.core.used)/\(.resources.core.limit) remaining: \(.resources.core.remaining)"'
