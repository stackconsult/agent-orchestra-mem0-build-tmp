# GitHub REST API Setup

## 🚀 Quick Setup

### 1. Install GitHub CLI (Already Done)
```bash
# GitHub CLI is installed: v2.86.0
gh --version
```

### 2. Authenticate with GitHub
```bash
gh auth login
```

### 3. Test the Setup
```bash
./test_github_api.sh
```

## 📁 Documentation Files

| File | Description |
|------|-------------|
| `docs/api/GITHUB_REST_API_DOCUMENTATION.md` | Comprehensive organized documentation |
| `docs/api/GITHUB_REST_API_OFFICIAL.md` | Official GitHub docs (HTML format) |
| `docs/api/QUICK_REFERENCE.md` | Quick reference guide |

## 🛠️ Scripts

### setup_github_api.sh
Sets up the GitHub API environment and downloads documentation.

```bash
./setup_github_api.sh
```

### test_github_api.sh
Tests GitHub API endpoints and verifies authentication.

```bash
./test_github_api.sh
```

## 📡 API Usage Examples

### Basic curl Request
```bash
curl --request GET \
     --url "https://api.github.com/user" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer $(gh auth token)" \
     --header "User-Agent: Your-App-Name"
```

### Using GitHub CLI (Recommended)
```bash
# Get user info
gh api user

# List repositories
gh api user/repos

# Get rate limits
gh api rate_limit

# Create an issue
gh api repos/owner/repo/issues --method POST --field title='New Issue' --field body='Issue description'
```

## 🔐 Authentication

### Personal Access Token
```bash
# Create a token
gh auth token

# Use token in curl
curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
```

### GitHub CLI Authentication
```bash
# Login (interactive)
gh auth login

# Check status
gh auth status

# Get current token
gh auth token
```

## 📊 Rate Limits

| Authentication | Requests/Hour |
|----------------|---------------|
| None | 60 |
| Personal Access Token | 5000 |
| GitHub App | 5000+ |

### Check Current Limits
```bash
gh api rate_limit
```

## 🎯 Common Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/user` | GET | Get authenticated user info |
| `/user/repos` | GET | List user repositories |
| `/repos/{owner}/{repo}` | GET | Get repository info |
| `/repos/{owner}/{repo}/issues` | GET | List repository issues |
| `/repos/{owner}/{repo}/issues` | POST | Create an issue |
| `/rate_limit` | GET | Get rate limit info |

## 🔍 Testing

### Run the Test Script
```bash
./test_github_api.sh
```

This will test:
- Authentication status
- User information retrieval
- Rate limit checking
- Repository listing
- Repository information

## 📚 Additional Resources

- [Official GitHub REST API Docs](https://docs.github.com/en/rest)
- [GitHub CLI Documentation](https://cli.github.com/)
- [Authentication Guide](https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api)

## 🚨 Important Notes

1. **Never expose tokens** in client-side code
2. **Use HTTPS** for all API requests
3. **Handle rate limits** gracefully
4. **Use appropriate HTTP methods** for actions
5. **Validate responses** and handle errors

## 🎉 Ready to Use

Your GitHub REST API environment is now set up and ready to use!

1. Authenticate: `gh auth login`
2. Test: `./test_github_api.sh`
3. Start making API requests!

---

*Setup completed on: $(date)*
*GitHub CLI version: $(gh --version)*
