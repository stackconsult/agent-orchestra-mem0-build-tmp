# GitHub REST API Documentation
## Getting Started with the REST API (API Version 2022-11-28)

### Overview
The GitHub REST API allows you to interact with GitHub programmatically. You can use it to create, read, update, and delete resources on GitHub, such as repositories, issues, pull requests, and more.

---

## 🔧 HTTP Methods

### Available HTTP Methods
The GitHub REST API uses standard HTTP methods to define actions on resources:

| **Method** | **Purpose** | **Example** |
|------------|------------|-------------|
| **GET** | Retrieve resources | `GET /repos/{owner}/{repo}/issues` |
| **POST** | Create resources | `POST /repos/{owner}/{repo}/issues` |
| **PATCH** | Update properties of resources | `PATCH /repos/{owner}/{repo}/issues/{issue_number}` |
| **PUT** | Replace resources or collections | `PUT /repos/{owner}/{repo}/contents/{path}` |
| **DELETE** | Delete resources | `DELETE /repos/{owner}/{repo}/issues/{issue_number}` |

### HTTP Method Usage
```bash
# GET example - List repository issues
GET /repos/{owner}/{repo}/issues

# POST example - Create an issue
POST /repos/{owner}/{repo}/issues

# PATCH example - Update an issue
PATCH /repos/{owner}/{repo}/issues/{issue_number}

# DELETE example - Delete an issue comment
DELETE /repos/{owner}/{repo}/issues/comments/{comment_id}
```

---

## 🛤️ API Paths

### Path Structure
Each endpoint has a path that defines the resource location. Path parameters are denoted by curly brackets `{}`.

### Example Path
```
/repos/{owner}/{repo}/issues
```

### Path Parameters
| **Parameter** | **Description** | **Example** |
|---------------|----------------|-------------|
| `{owner}` | Repository owner's username | `octocat` |
| `{repo}` | Repository name | `Hello-World` |
| `{issue_number}` | Issue number | `42` |

### Complete URL Structure
```
https://api.github.com/PATH
```

**Example:**
```bash
https://api.github.com/repos/octocat/Hello-World/issues
```

---

## 📋 Request Headers

### Required Headers

#### Accept Header
Specifies the media type for the response format.

```bash
Accept: application/vnd.github+json
```

#### X-GitHub-Api-Version Header
Specifies the API version to use.

```bash
X-GitHub-Api-Version: 2022-11-28
```

#### User-Agent Header
Identifies the application making the request.

```bash
User-Agent: Awesome-Octocat-App
```

### Authentication Header
Required for authenticated requests.

```bash
Authorization: Bearer YOUR_TOKEN
# or
Authorization: token YOUR_TOKEN
```

---

## 🎯 Media Types

### Common Media Types

| **Media Type** | **Description** | **Usage** |
|----------------|-----------------|----------|
| `application/vnd.github+json` | Standard GitHub JSON format | Most endpoints |
| `application/json` | Standard JSON format | Basic endpoints |
| `application/vnd.github.diff+json` | Git diff format | Commit/PR endpoints |
| `application/vnd.github.patch+json` | Git patch format | Commit/PR endpoints |
| `application/vnd.github.sha+json` | SHA format | Commit endpoints |
| `application/vnd.github.raw+json` | Raw content format | File content endpoints |
| `application/vnd.github.html+json` | HTML format | Rendering endpoints |

### Custom Media Types Format
```
application/vnd.github.PARAM+json
```

**Examples:**
```bash
Accept: application/vnd.github.diff+json
Accept: application/vnd.github.raw+json
Accept: application/vnd.github.sha+json
```

---

## 🔐 Authentication

### Authentication Methods

#### 1. Personal Access Token
```bash
Authorization: Bearer ghp_YOUR_PERSONAL_ACCESS_TOKEN
```

#### 2. GitHub App Token
```bash
Authorization: Bearer v1.YOUR_GITHUB_APP_TOKEN
```

#### 3. GitHub Actions Token
```bash
Authorization: Bearer ${{ secrets.GITHUB_TOKEN }}
```

#### 4. JWT (JSON Web Token)
```bash
Authorization: Bearer YOUR_JWT_TOKEN
```

### Authentication Benefits
- **Higher Rate Limits**: 5000 requests/hour (vs. 60 unauthenticated)
- **Access to Private Resources**: Private repositories, organizations
- **Additional Data**: More detailed responses
- **Write Access**: Create, update, delete resources

---

## 🚀 Making Requests with curl

### Basic curl Request Structure
```bash
curl --request METHOD \
     --url "https://api.github.com/PATH" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: YOUR_APP_NAME"
```

### curl Options Reference

| **Option** | **Short** | **Description** | **Example** |
|------------|-----------|-----------------|-------------|
| `--request` | `-X` | HTTP method | `--request GET` |
| `--url` | | Full API URL | `--url "https://api.github.com/user"` |
| `--header` | `-H` | Request header | `--header "Accept: application/vnd.github+json"` |
| `--data` | `-d` | Request body (JSON) | `--data '{"title":"My Issue"}'` |

---

## 📝 Query Parameters

### Basic Query Parameters
```bash
# Single parameter
https://api.github.com/repos/octocat/Hello-World/issues?state=open

# Multiple parameters
https://api.github.com/repos/octocat/Hello-World/issues?state=open&labels=bug,urgent

# Array parameters
https://api.github.com/search/repositories?q=language:python&sort=stars&order=desc
```

### Array Parameters Format
```bash
# Array with multiple values
?repository_ids[]=REPO_A_ID&repository_ids[]=REPO_B_ID

# Example
https://api.github.com/user/repos?visibility=all&affiliation=owner,collaborator
```

---

## 📦 Request Body Parameters

### JSON Body Example
```bash
curl --request POST \
     --url "https://api.github.com/repos/octocat/Hello-World/issues" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App" \
     --data '{
       "title": "Found a bug",
       "body": "I'\''m having a problem with this.",
       "labels": ["bug", "urgent"],
       "assignees": ["octocat"]
     }'
```

---

## 📊 Response Handling

### Response Codes
| **Code** | **Meaning** | **Action** |
|----------|-------------|------------|
| `200 OK` | Success | Process response |
| `201 Created` | Resource created | Process response |
| `204 No Content` | Success, no content | Action completed |
| `400 Bad Request` | Invalid request | Fix request |
| `401 Unauthorized` | Authentication required | Add auth |
| `403 Forbidden` | Permission denied | Check permissions |
| `404 Not Found` | Resource not found | Verify path |
| `422 Unprocessable Entity` | Validation error | Fix data |
| `429 Rate Limited` | Too many requests | Wait/retry |

### Response Headers
```bash
# Rate limit information
X-RateLimit-Limit: 5000
X-RateLimit-Remaining: 4999
X-RateLimit-Reset: 1640995200

# Pagination
Link: <https://api.github.com/user/repos?page=2>; rel="next"

# API version
X-GitHub-Media-Type: application/vnd.github+json
```

---

## 🔍 Example Requests

### 1. Get User Information
```bash
curl --request GET \
     --url "https://api.github.com/user" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App"
```

### 2. List Repository Issues
```bash
curl --request GET \
     --url "https://api.github.com/repos/octocat/Hello-World/issues?state=open" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App"
```

### 3. Create an Issue
```bash
curl --request POST \
     --url "https://api.github.com/repos/octocat/Hello-World/issues" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App" \
     --data '{
       "title": "New Issue Title",
       "body": "Issue description here",
       "labels": ["bug"]
     }'
```

### 4. Update an Issue
```bash
curl --request PATCH \
     --url "https://api.github.com/repos/octocat/Hello-World/issues/42" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App" \
     --data '{
       "state": "closed",
       "labels": ["bug", "fixed"]
     }'
```

### 5. Get Repository Content
```bash
curl --request GET \
     --url "https://api.github.com/repos/octocat/Hello-World/contents/README.md" \
     --header "Accept: application/vnd.github.raw+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App"
```

---

## 📈 Rate Limiting

### Rate Limits
| **Authentication** | **Requests per Hour** |
|-------------------|----------------------|
| Unauthenticated | 60 |
| Authenticated | 5000 |
| GitHub App | 5000+ (varies) |

### Checking Rate Limits
```bash
curl --request GET \
     --url "https://api.github.com/rate_limit" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App"
```

### Rate Limit Response
```json
{
  "resources": {
    "core": {
      "limit": 5000,
      "remaining": 4999,
      "reset": 1640995200,
      "used": 1
    }
  }
}
```

---

## 🔄 Pagination

### Pagination Methods
1. **Link Header** (Recommended)
2. **Page/Per Page Parameters**

### Link Header Pagination
```bash
# Response includes Link header
Link: <https://api.github.com/user/repos?page=2>; rel="next",
      <https://api.github.com/user/repos?page=5>; rel="last"
```

### Page Parameters
```bash
# Page and per_page parameters
https://api.github.com/user/repos?page=2&per_page=100
```

### Pagination Example
```bash
curl --request GET \
     --url "https://api.github.com/user/repos?page=1&per_page=50" \
     --header "Accept: application/vnd.github+json" \
     --header "X-GitHub-Api-Version: 2022-11-28" \
     --header "Authorization: Bearer YOUR_TOKEN" \
     --header "User-Agent: Awesome-Octocat-App"
```

---

## 🛠️ Error Handling

### Common Error Responses

#### 401 Unauthorized
```json
{
  "message": "Requires authentication",
  "documentation_url": "https://docs.github.com/rest"
}
```

#### 403 Forbidden
```json
{
  "message": "API rate limit exceeded",
  "documentation_url": "https://docs.github.com/rest"
}
```

#### 404 Not Found
```json
{
  "message": "Not Found",
  "documentation_url": "https://docs.github.com/rest"
}
```

#### 422 Unprocessable Entity
```json
{
  "message": "Validation Failed",
  "errors": [
    {
      "resource": "Issue",
      "field": "title",
      "code": "missing_field"
    }
  ]
}
```

---

## 🔧 Best Practices

### Security
1. **Never expose tokens** in client-side code
2. **Use HTTPS** for all API requests
3. **Validate input** data before sending
4. **Use least privilege** principle for token scopes

### Performance
1. **Use pagination** for large result sets
2. **Cache responses** when appropriate
3. **Use conditional requests** with ETags
4. **Batch operations** when possible

### Reliability
1. **Handle rate limits** gracefully
2. **Implement retry logic** for transient errors
3. **Use appropriate HTTP methods**
4. **Validate response schemas**

---

## 📚 Additional Resources

### Official Documentation
- [GitHub REST API Overview](https://docs.github.com/en/rest)
- [Authentication Guide](https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api)
- [API Versions](https://docs.github.com/en/rest/overview/api-versions)
- [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting)

### Tools and Libraries
- [GitHub CLI](https://cli.github.com/)
- [Octokit.js](https://github.com/octokit/octokit.js)
- [PyGithub](https://github.com/PyGithub/PyGithub)
- [go-github](https://github.com/google/go-github)

### Community Resources
- [GitHub API Community Forum](https://github.com/orgs/community/discussions/categories/api)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/github-api)
- [GitHub API Changelog](https://docs.github.com/en/rest/overview/changelog)

---

## 🚀 Quick Start Checklist

### Before You Start
- [ ] Create a GitHub Personal Access Token
- [ ] Install curl or an API client
- [ ] Choose your authentication method
- [ ] Review rate limits for your use case

### First Request
- [ ] Set up proper headers
- [ ] Make a simple GET request to `/user`
- [ ] Verify authentication works
- [ ] Check rate limit status

### Next Steps
- [ ] Explore endpoints for your use case
- [ ] Implement error handling
- [ ] Set up pagination for large datasets
- [ ] Monitor rate limits

---

*This documentation covers the GitHub REST API with API version 2022-11-28. For the most up-to-date information, always refer to the official GitHub REST API documentation.*
