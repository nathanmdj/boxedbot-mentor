# BoxedBot Technical Architecture

## System Overview

BoxedBot is a serverless AI-powered GitHub PR reviewer built on Modal.com with FastAPI, designed for scalability, cost-effectiveness, and ease of deployment.

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│    GitHub       │───▶│   Modal.com      │───▶│   OpenAI API    │
│    Webhooks     │    │   (FastAPI)      │    │   (GPT-4o)      │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │                  │
                       │   GitHub API     │
                       │   (Comments)     │
                       │                  │
                       └──────────────────┘
```

### Core Components

1. **Webhook Handler**: Receives and processes GitHub events
2. **PR Analyzer**: Analyzes code changes using AI
3. **Comment Generator**: Creates and posts review comments
4. **Configuration Manager**: Handles per-repository settings
5. **Authentication Layer**: Manages GitHub App authentication

## Technology Stack

### Platform & Framework
- **Modal.com**: Serverless deployment platform
  - Auto-scaling functions
  - Built-in secrets management
  - Cost-effective pay-per-use pricing
  - Excellent cold start performance

- **FastAPI**: Python web framework
  - High performance async support
  - Automatic API documentation
  - Built-in request validation
  - Native Pydantic integration

### AI & External Services
- **OpenAI GPT-4o/4o-mini**: Code analysis and review generation
- **GitHub API**: Repository access and webhook management
- **GitHub App**: Secure authentication and permissions

### Development Tools
- **Modal CLI**: Local development and deployment
- **Pydantic**: Data validation and serialization
- **Python 3.11+**: Runtime environment

## Modal.com Integration Details

### Function Architecture

```python
import modal

# Create Modal app
app = modal.App("boxedbot")

# Define container image with dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi",
    "openai", 
    "PyGithub",
    "cryptography",
    "pydantic"
)
```

### Key Modal Patterns

**1. FastAPI Endpoints**
```python
@app.function(image=image, secrets=[modal.Secret.from_name("github-app")])
@modal.fastapi_endpoint(method="POST")
async def github_webhook(request: Request):
    """Handle GitHub webhook events"""
    # Webhook signature verification
    # Event routing and processing
    return {"status": "processed"}
```

**2. Background Processing**
```python
@app.function(
    image=image, 
    secrets=[modal.Secret.from_name("openai-api"), modal.Secret.from_name("github-app")],
    timeout=300  # 5 minute timeout for AI analysis
)
async def analyze_pull_request(pr_data: dict):
    """Analyze PR with AI and post comments"""
    # Fetch PR diff
    # Analyze with OpenAI
    # Post review comments
```

**3. Configuration Management**
```python
@app.function(image=image)
@modal.fastapi_endpoint(method="GET")
async def get_repo_config(repo_id: str):
    """Retrieve repository configuration"""
    # Load config from persistent storage
    return config_data
```

### Secrets Management

Modal secrets are used for sensitive configuration:

```python
# GitHub App credentials
github_secret = modal.Secret.from_dict({
    "GITHUB_APP_ID": "123456",
    "GITHUB_PRIVATE_KEY": "-----BEGIN RSA PRIVATE KEY-----...",
    "GITHUB_WEBHOOK_SECRET": "webhook_secret_key"
})

# OpenAI API key
openai_secret = modal.Secret.from_dict({
    "OPENAI_API_KEY": "sk-..."
})
```

## Data Flow Architecture

### 1. Webhook Processing Flow

```
GitHub Event → Modal Webhook Handler → Event Validation → Background Processing
                      ↓
Event Types:
- pull_request.opened
- pull_request.synchronize  
- pull_request.reopened
```

### 2. PR Analysis Pipeline

```
PR Event → Fetch PR Data → Get Repository Config → Analyze Diff → Generate Review → Post Comments
    ↓            ↓              ↓                    ↓              ↓            ↓
GitHub API   GitHub API    Config Storage      OpenAI API    AI Processing   GitHub API
```

### 3. Configuration Management

```
Admin Request → Validate Config → Store Settings → Apply to Future PRs
      ↓              ↓                ↓                  ↓
  FastAPI        Pydantic       Persistent Store    PR Analyzer
```

## Component Deep Dive

### Webhook Handler

**Responsibilities**:
- Verify GitHub webhook signatures
- Parse and validate webhook payloads
- Route events to appropriate processors
- Handle rate limiting and retries

**Implementation**:
```python
@app.function(image=image, secrets=[modal.Secret.from_name("github-app")])
@modal.fastapi_endpoint(method="POST", path="/webhooks/github")
async def handle_github_webhook(request: Request):
    # Signature verification
    signature = request.headers.get("X-Hub-Signature-256")
    payload = await request.body()
    
    if not verify_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse webhook event
    event_type = request.headers.get("X-GitHub-Event")
    data = await request.json()
    
    # Route to appropriate handler
    if event_type == "pull_request":
        await handle_pr_event.call(data)
    
    return {"status": "received"}
```

### PR Analyzer

**Responsibilities**:
- Fetch PR diffs and metadata
- Apply repository-specific configuration
- Generate AI-powered analysis
- Create structured review comments

**AI Analysis Pipeline**:
```python
async def analyze_code_changes(diff_content: str, file_path: str) -> List[ReviewComment]:
    prompt = f"""
    Analyze this code diff for a {file_path} file:
    
    {diff_content}
    
    Provide specific, actionable feedback focusing on:
    1. Code quality and best practices
    2. Potential security vulnerabilities  
    3. Performance issues
    4. Maintainability concerns
    
    Format as JSON array of comments with line numbers.
    """
    
    response = await openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    return parse_ai_response(response.choices[0].message.content)
```

### Comment Generator

**Responsibilities**:
- Format AI suggestions into GitHub-compatible comments
- Avoid duplicate comments on the same lines
- Handle comment threading and updates
- Manage comment lifecycle (create, update, resolve)

### Configuration Manager

**Responsibilities**:
- Store per-repository settings
- Validate configuration changes
- Provide default configurations
- Handle configuration inheritance

**Configuration Schema**:
```python
class RepoConfig(BaseModel):
    enabled: bool = True
    file_patterns: List[str] = ["*.py", "*.js", "*.ts", "*.go", "*.rs"]
    exclude_patterns: List[str] = ["node_modules/**", "*.min.js"]
    review_level: str = "standard"  # minimal, standard, strict
    focus_areas: List[str] = ["security", "performance", "style"]
    auto_approve_minor: bool = False
    max_comments_per_pr: int = 20
```

## Security Architecture

### Authentication Flow

1. **GitHub App Installation**: Repository admin installs BoxedBot
2. **Webhook Registration**: GitHub sends events to Modal endpoints
3. **Token Management**: GitHub App JWT tokens for API access
4. **Signature Verification**: All webhooks verified with shared secret

### Security Measures

**1. Webhook Security**:
```python
import hmac
import hashlib

def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(), 
        payload, 
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

**2. API Authentication**:
```python
from github import Github
import jwt

def get_github_client(installation_id: int) -> Github:
    # Create JWT token
    jwt_token = jwt.encode({
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "iss": GITHUB_APP_ID
    }, GITHUB_PRIVATE_KEY, algorithm="RS256")
    
    # Get installation access token
    auth = Auth.Token(jwt_token)
    gi = GithubIntegration(auth=auth)
    access_token = gi.get_access_token(installation_id)
    
    return Github(access_token.token)
```

### Permission Model

**GitHub App Permissions**:
- Repository permissions: Read (metadata, code, pull requests)
- Repository permissions: Write (pull requests for comments)
- Account permissions: None (minimize scope)

## Scalability & Performance

### Modal.com Scaling

**Auto-scaling Features**:
- Functions scale from 0 to hundreds of instances
- Cold start optimization with container reuse
- Concurrent request handling per function

**Performance Optimizations**:
```python
# Concurrent PR analysis
@app.function(
    image=image,
    concurrency_limit=10,  # Max 10 concurrent analyses
    timeout=300,
    memory=1024  # 1GB memory for AI processing
)
async def analyze_pr_concurrent(pr_data: dict):
    # Process multiple files in parallel
    tasks = [analyze_file(file_diff) for file_diff in pr_data["files"]]
    results = await asyncio.gather(*tasks)
    return combine_results(results)
```

### Cost Optimization

**1. AI Usage Optimization**:
- Use GPT-4o-mini for most analyses
- Implement prompt caching for similar code patterns  
- Batch small files for analysis
- Skip generated or vendor files

**2. Caching Strategy**:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_file_analysis_prompt(file_type: str, analysis_type: str) -> str:
    """Cache prompt templates to avoid regeneration"""
    return generate_prompt_template(file_type, analysis_type)
```

## Error Handling & Reliability

### Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def post_review_comment(github_client, pr, comment):
    """Post comment with retry logic"""
    try:
        return await github_client.create_review_comment(pr, comment)
    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        raise
```

### Error Monitoring

```python
import logging
from modal import Secret

logger = logging.getLogger(__name__)

@app.function(image=image, secrets=[Secret.from_name("logging-config")])
async def handle_error(error_data: dict):
    """Centralized error handling and logging"""
    logger.error(f"BoxedBot error: {error_data}", extra={
        "repo": error_data.get("repository"),
        "pr": error_data.get("pull_request_id"),
        "error_type": error_data.get("error_type")
    })
```

## Deployment Architecture

### Development Environment

```bash
# Local development with Modal
modal serve app.py

# This creates temporary endpoints for testing:
# https://username--boxedbot-dev.modal.run/webhooks/github
```

### Production Deployment

```bash
# Deploy to Modal cloud
modal deploy app.py

# Creates stable production endpoints:
# https://username--boxedbot.modal.run/webhooks/github
```

### Environment Configuration

```python
# app.py
import os
from modal import Secret

# Environment-specific configuration
if os.getenv("MODAL_ENVIRONMENT") == "dev":
    secrets = [Secret.from_name("dev-secrets")]
    webhook_url = "dev-webhook-url"
else:
    secrets = [Secret.from_name("prod-secrets")]  
    webhook_url = "prod-webhook-url"
```

## Monitoring & Observability

### Health Checks

```python
@app.function(image=image)
@modal.fastapi_endpoint(method="GET", path="/health")
async def health_check():
    """Service health check endpoint"""
    try:
        # Check external dependencies
        await check_github_api()
        await check_openai_api()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
```

### Metrics Collection

```python
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def track_processing_time(operation: str):
    """Track operation timing"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation} completed in {duration:.2f}s")
```

## Data Storage Strategy

### Configuration Storage

Modal provides limited persistent storage, so configuration can be:
1. **Environment Variables**: For simple settings
2. **External Database**: For complex configurations (optional)
3. **GitHub Repository Files**: Store config in `.boxedbot.yml`

### Example Repository Configuration

```yaml
# .boxedbot.yml
version: "1.0"
enabled: true
files:
  include: ["src/**/*.py", "tests/**/*.py"]
  exclude: ["**/migrations/**", "**/__pycache__/**"]
review:
  level: "standard"
  focus: ["security", "performance"] 
  max_comments: 15
ai:
  model: "gpt-4o-mini"
  temperature: 0.1
```

This architecture provides a robust, scalable foundation for BoxedBot that leverages Modal.com's serverless capabilities while maintaining security, performance, and cost-effectiveness.