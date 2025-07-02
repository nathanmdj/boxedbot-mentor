# BoxedBot API Documentation

## Overview

BoxedBot provides a RESTful API built with FastAPI for handling GitHub webhooks, managing repository configurations, and monitoring service health. All endpoints are deployed on Modal.com and automatically scale based on demand.

**Base URL**: `https://your-username--boxedbot.modal.run`

## Authentication

### GitHub Webhook Authentication

All webhook endpoints use GitHub's signature-based authentication:

```http
X-Hub-Signature-256: sha256=<signature>
X-GitHub-Event: <event_type>
```

Signatures are verified using HMAC-SHA256 with the webhook secret configured in your GitHub App.

### GitHub App Authentication

Internal API calls to GitHub use JWT-based GitHub App authentication:

1. Generate JWT token signed with GitHub App private key
2. Exchange JWT for installation access token
3. Use access token for GitHub API calls

## Webhook Endpoints

### POST /webhooks/github

Handles GitHub webhook events for pull request analysis.

**Headers**:
```http
Content-Type: application/json
X-Hub-Signature-256: sha256=<hmac_signature>
X-GitHub-Event: <event_type>
X-GitHub-Delivery: <delivery_id>
```

**Supported Events**:
- `pull_request` (actions: opened, synchronize, reopened)
- `pull_request_review` (for future features)

**Request Body** (Pull Request Event):
```json
{
  "action": "opened",
  "pull_request": {
    "id": 123456789,
    "number": 42,
    "title": "Add new feature",
    "body": "This PR adds...",
    "head": {
      "sha": "abc123def456",
      "ref": "feature-branch"
    },
    "base": {
      "sha": "def456abc123",
      "ref": "main"
    }
  },
  "repository": {
    "id": 987654321,
    "name": "my-repo",
    "full_name": "owner/my-repo",
    "owner": {
      "login": "owner"
    }
  },
  "installation": {
    "id": 12345678
  }
}
```

**Response**:
```json
{
  "status": "processing",
  "action": "opened",
  "pr_id": 123456789,
  "message": "PR analysis queued for processing"
}
```

**Error Responses**:
```json
// Invalid signature
{
  "detail": "Invalid signature",
  "status_code": 401
}

// Missing signature
{
  "detail": "Missing signature", 
  "status_code": 401
}

// Unsupported event
{
  "status": "ignored",
  "event_type": "issues",
  "message": "Event type not supported"
}
```

## Health Check Endpoints

### GET /health

Service health check endpoint for monitoring and load balancers.

**Response**:
```json
{
  "status": "healthy",
  "service": "boxedbot",
  "version": "1.0.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "dependencies": {
    "github_api": "healthy",
    "openai_api": "healthy"
  }
}
```

**Error Response** (Service Unhealthy):
```json
{
  "status": "unhealthy",
  "service": "boxedbot", 
  "error": "OpenAI API connection failed",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### GET /health/detailed

Detailed health check with dependency status.

**Response**:
```json
{
  "status": "healthy",
  "service": "boxedbot",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "dependencies": {
    "github_api": {
      "status": "healthy",
      "response_time_ms": 150,
      "last_check": "2024-01-15T10:29:55Z"
    },
    "openai_api": {
      "status": "healthy", 
      "response_time_ms": 300,
      "last_check": "2024-01-15T10:29:58Z"
    }
  },
  "metrics": {
    "total_prs_analyzed": 1250,
    "active_installations": 45,
    "avg_response_time_ms": 1800
  }
}
```

## Configuration Endpoints

### GET /config/{repo_id}

Retrieve configuration for a specific repository.

**Parameters**:
- `repo_id` (path): Repository ID or "owner/repo" format

**Headers**:
```http
Authorization: Bearer <github_app_token>
```

**Response**:
```json
{
  "repo_id": "owner/my-repo",
  "config": {
    "enabled": true,
    "file_patterns": [
      "*.py",
      "*.js", 
      "*.ts"
    ],
    "exclude_patterns": [
      "node_modules/**",
      "*.min.js",
      "__pycache__/**"
    ],
    "review_level": "standard",
    "focus_areas": [
      "security",
      "performance", 
      "style"
    ],
    "max_comments_per_pr": 20,
    "ai_model": "gpt-4o-mini"
  },
  "last_updated": "2024-01-15T09:00:00Z"
}
```

### POST /config/{repo_id}

Update configuration for a specific repository.

**Parameters**:
- `repo_id` (path): Repository ID or "owner/repo" format

**Headers**:
```http
Authorization: Bearer <github_app_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "enabled": true,
  "file_patterns": [
    "src/**/*.py",
    "tests/**/*.py"
  ],
  "exclude_patterns": [
    "**/migrations/**",
    "**/__pycache__/**"
  ],
  "review_level": "strict",
  "focus_areas": [
    "security",
    "performance"
  ],
  "max_comments_per_pr": 15,
  "ai_model": "gpt-4o"
}
```

**Response**:
```json
{
  "status": "updated",
  "repo_id": "owner/my-repo",
  "config": {
    "enabled": true,
    "file_patterns": [
      "src/**/*.py",
      "tests/**/*.py"
    ],
    "exclude_patterns": [
      "**/migrations/**",
      "**/__pycache__/**"
    ],
    "review_level": "strict",
    "focus_areas": [
      "security",
      "performance"
    ],
    "max_comments_per_pr": 15,
    "ai_model": "gpt-4o"
  },
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### DELETE /config/{repo_id}

Reset repository configuration to defaults.

**Parameters**:
- `repo_id` (path): Repository ID or "owner/repo" format

**Response**:
```json
{
  "status": "reset",
  "repo_id": "owner/my-repo",
  "message": "Configuration reset to defaults"
}
```

## Analytics Endpoints

### GET /analytics/{repo_id}

Get analytics data for a repository.

**Parameters**:
- `repo_id` (path): Repository ID or "owner/repo" format
- `start_date` (query): Start date (ISO 8601 format)
- `end_date` (query): End date (ISO 8601 format)
- `granularity` (query): "day", "week", or "month"

**Response**:
```json
{
  "repo_id": "owner/my-repo",
  "period": {
    "start": "2024-01-01T00:00:00Z",
    "end": "2024-01-15T23:59:59Z"
  },
  "metrics": {
    "total_prs_analyzed": 45,
    "avg_response_time_seconds": 95,
    "comments_posted": 180,
    "issues_found": {
      "security": 12,
      "performance": 8,
      "style": 89,
      "maintainability": 71
    },
    "ai_cost_usd": 2.35
  },
  "trends": [
    {
      "date": "2024-01-01",
      "prs_analyzed": 3,
      "comments_posted": 12,
      "avg_response_time": 87
    }
  ]
}
```

### GET /analytics/global

Get global analytics across all installations.

**Response**:
```json
{
  "total_installations": 156,
  "active_repositories": 89,
  "global_metrics": {
    "total_prs_analyzed": 12450,
    "avg_response_time_seconds": 92,
    "total_comments_posted": 45230,
    "total_ai_cost_usd": 234.50
  },
  "top_languages": [
    {"language": "Python", "usage_percent": 35.2},
    {"language": "JavaScript", "usage_percent": 28.7},
    {"language": "TypeScript", "usage_percent": 18.9}
  ]
}
```

## Installation Management

### POST /install/{installation_id}

Handle new GitHub App installation.

**Parameters**:
- `installation_id` (path): GitHub installation ID

**Request Body**:
```json
{
  "account": {
    "login": "owner",
    "type": "Organization"
  },
  "repositories": [
    {
      "id": 123456789,
      "name": "my-repo",
      "full_name": "owner/my-repo"
    }
  ]
}
```

**Response**:
```json
{
  "status": "installed",
  "installation_id": 12345678,
  "repositories_configured": 1,
  "webhook_url": "https://your-username--boxedbot.modal.run/webhooks/github"
}
```

### DELETE /install/{installation_id}

Handle GitHub App uninstallation.

**Parameters**:
- `installation_id` (path): GitHub installation ID

**Response**:
```json
{
  "status": "uninstalled",
  "installation_id": 12345678,
  "repositories_removed": 3
}
```

## Error Handling

### Error Response Format

All API errors follow a consistent format:

```json
{
  "error": {
    "code": "INVALID_CONFIGURATION",
    "message": "Review level must be one of: minimal, standard, strict",
    "details": {
      "field": "review_level",
      "provided_value": "invalid_level"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123def456"
}
```

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request format or parameters
- `401 Unauthorized` - Authentication failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Valid request but business logic error
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service temporarily unavailable

### Common Error Codes

- `INVALID_SIGNATURE` - Webhook signature verification failed
- `MISSING_AUTHENTICATION` - Required authentication headers missing
- `INVALID_CONFIGURATION` - Configuration validation failed
- `REPOSITORY_NOT_FOUND` - Repository not accessible
- `RATE_LIMIT_EXCEEDED` - API rate limit exceeded
- `AI_SERVICE_UNAVAILABLE` - OpenAI API unavailable
- `GITHUB_API_ERROR` - GitHub API returned error

## Rate Limiting

API endpoints are subject to rate limiting to ensure fair usage:

### Rate Limit Headers

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642248000
X-RateLimit-Retry-After: 60
```

### Rate Limits by Endpoint

- **Webhook endpoints**: 100 requests per minute per installation
- **Configuration endpoints**: 60 requests per hour per repository
- **Analytics endpoints**: 20 requests per minute per user
- **Health check endpoints**: No rate limiting

### Rate Limit Exceeded Response

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "retry_after_seconds": 60
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## SDK Usage Examples

### Python SDK (using requests)

```python
import requests
import hmac
import hashlib
import json

class BoxedBotAPI:
    def __init__(self, base_url: str, webhook_secret: str = None):
        self.base_url = base_url
        self.webhook_secret = webhook_secret
    
    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not self.webhook_secret:
            return False
        
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    def get_health(self) -> dict:
        """Get service health status"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def get_repo_config(self, repo_id: str, token: str) -> dict:
        """Get repository configuration"""
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{self.base_url}/config/{repo_id}",
            headers=headers
        )
        return response.json()
    
    def update_repo_config(self, repo_id: str, config: dict, token: str) -> dict:
        """Update repository configuration"""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"{self.base_url}/config/{repo_id}",
            json=config,
            headers=headers
        )
        return response.json()

# Usage example
api = BoxedBotAPI("https://your-username--boxedbot.modal.run")

# Check health
health = api.get_health()
print(f"Service status: {health['status']}")

# Update repository configuration
config = {
    "enabled": True,
    "review_level": "strict",
    "focus_areas": ["security", "performance"]
}
result = api.update_repo_config("owner/repo", config, "github_token")
print(f"Config updated: {result['status']}")
```

### JavaScript SDK (using fetch)

```javascript
class BoxedBotAPI {
    constructor(baseUrl, webhookSecret = null) {
        this.baseUrl = baseUrl;
        this.webhookSecret = webhookSecret;
    }
    
    async verifyWebhook(payload, signature) {
        if (!this.webhookSecret) return false;
        
        const crypto = require('crypto');
        const expected = crypto
            .createHmac('sha256', this.webhookSecret)
            .update(payload)
            .digest('hex');
        
        return crypto.timingSafeEqual(
            Buffer.from(`sha256=${expected}`),
            Buffer.from(signature)
        );
    }
    
    async getHealth() {
        const response = await fetch(`${this.baseUrl}/health`);
        return response.json();
    }
    
    async getRepoConfig(repoId, token) {
        const response = await fetch(`${this.baseUrl}/config/${repoId}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        return response.json();
    }
    
    async updateRepoConfig(repoId, config, token) {
        const response = await fetch(`${this.baseUrl}/config/${repoId}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        return response.json();
    }
}

// Usage example
const api = new BoxedBotAPI('https://your-username--boxedbot.modal.run');

// Check health
api.getHealth().then(health => {
    console.log(`Service status: ${health.status}`);
});

// Update configuration
const config = {
    enabled: true,
    review_level: 'strict',
    focus_areas: ['security', 'performance']
};

api.updateRepoConfig('owner/repo', config, 'github_token').then(result => {
    console.log(`Config updated: ${result.status}`);
});
```

## Webhook Testing

### Testing with ngrok (Development)

1. **Install ngrok**: `npm install -g ngrok`
2. **Expose local development**: `ngrok http 8000`
3. **Update GitHub webhook URL**: Use ngrok URL in GitHub App settings
4. **Test webhook delivery**: Use GitHub's webhook delivery testing

### Testing with curl

```bash
# Test health endpoint
curl -X GET "https://your-username--boxedbot.modal.run/health"

# Test webhook endpoint (with proper signature)
curl -X POST "https://your-username--boxedbot.modal.run/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=<signature>" \
  -d '{"action":"opened","pull_request":{"id":123}}'
```

## OpenAPI Specification

BoxedBot automatically generates OpenAPI (Swagger) documentation at:
- **Interactive docs**: `https://your-username--boxedbot.modal.run/docs`
- **ReDoc**: `https://your-username--boxedbot.modal.run/redoc`
- **OpenAPI JSON**: `https://your-username--boxedbot.modal.run/openapi.json`

This comprehensive API documentation provides all the information needed to integrate with and extend BoxedBot's functionality.