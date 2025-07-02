# BoxedBot Implementation Guide

## Getting Started

This guide provides step-by-step instructions for implementing BoxedBot, from initial setup to production deployment.

## Prerequisites

### Required Accounts & Services

1. **Modal.com Account**
   - Sign up at [modal.com](https://modal.com)
   - Install Modal CLI: `pip install modal`
   - Authenticate: `modal setup`

2. **GitHub Account/Organization**
   - Admin access to repositories where BoxedBot will be installed
   - Ability to create GitHub Apps

3. **OpenAI Account**
   - API access with billing enabled
   - API key with sufficient credits

### Development Environment

```bash
# Python 3.11+ required
python --version  # Should be 3.11 or higher

# Install dependencies
pip install modal fastapi openai PyGithub python-jose cryptography pydantic
```

## Phase 1: Project Setup

### 1.1 Initialize Modal Project

```bash
# Create project directory
mkdir boxedbot
cd boxedbot

# Initialize git repository
git init
```

### 1.2 Create Basic Project Structure

```
boxedbot/
├── app.py              # Main Modal application
├── src/
│   ├── __init__.py
│   ├── webhook_handler.py    # GitHub webhook processing
│   ├── pr_analyzer.py        # PR analysis logic
│   ├── comment_generator.py  # Comment creation and posting
│   ├── config_manager.py     # Repository configuration
│   └── auth.py              # GitHub authentication
├── tests/
│   ├── __init__.py
│   ├── test_webhook.py
│   ├── test_analyzer.py
│   └── test_config.py
├── prompts/
│   ├── code_review.txt      # AI prompts for code review
│   └── security_review.txt  # Security-focused prompts
├── requirements.txt
└── README.md
```

### 1.3 Create Main Application File

```python
# app.py
import modal
from fastapi import FastAPI, Request, HTTPException
from src.webhook_handler import WebhookHandler
from src.auth import GitHubAuth

# Create Modal app
app = modal.App("boxedbot")

# Define container image
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "fastapi==0.104.1",
    "openai==1.3.7", 
    "PyGithub==1.59.1",
    "python-jose[cryptography]==3.3.0",
    "pydantic==2.5.0",
    "httpx==0.25.2"
)

# Initialize FastAPI app for endpoints
web_app = FastAPI(title="BoxedBot API", version="1.0.0")

@web_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "boxedbot"}

@web_app.post("/webhooks/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events"""
    handler = WebhookHandler()
    return await handler.process_webhook(request)

# Mount FastAPI app to Modal
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("github-app-secrets"),
        modal.Secret.from_name("openai-secrets")
    ],
    allow_concurrent_inputs=100
)
@modal.asgi_app()
def fastapi_app():
    return web_app
```

## Phase 2: GitHub App Setup

### 2.1 Create GitHub App

1. **Navigate to GitHub App Creation**:
   - Go to GitHub Settings → Developer settings → GitHub Apps
   - Click "New GitHub App"

2. **Configure App Settings**:
   ```
   App Name: BoxedBot
   Homepage URL: https://your-domain.com (or GitHub repo)
   Webhook URL: https://your-username--boxedbot.modal.run/webhooks/github
   Webhook Secret: [Generate a secure random string]
   ```

3. **Set Permissions**:
   ```
   Repository Permissions:
   - Contents: Read
   - Issues: Read  
   - Metadata: Read
   - Pull requests: Write
   - Commit statuses: Read
   
   Subscribe to Events:
   - Pull request
   - Pull request review
   ```

4. **Download Private Key**:
   - Generate and download the private key (.pem file)
   - Store securely for Modal secrets setup

### 2.2 Configure Modal Secrets

```bash
# Create GitHub App secrets
modal secret create github-app-secrets \
  GITHUB_APP_ID="your_app_id" \
  GITHUB_PRIVATE_KEY="$(cat path/to/private-key.pem)" \
  GITHUB_WEBHOOK_SECRET="your_webhook_secret"

# Create OpenAI secrets  
modal secret create openai-secrets \
  OPENAI_API_KEY="sk-your-openai-api-key"
```

## Phase 3: Core Implementation

### 3.1 Webhook Handler Implementation

```python
# src/webhook_handler.py
import json
import hmac
import hashlib
import os
from fastapi import Request, HTTPException
from .pr_analyzer import PRAnalyzer

class WebhookHandler:
    def __init__(self):
        self.webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        self.pr_analyzer = PRAnalyzer()
    
    async def process_webhook(self, request: Request):
        """Process incoming GitHub webhook"""
        # Verify signature
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        
        payload = await request.body()
        if not self._verify_signature(payload, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event
        event_type = request.headers.get("X-GitHub-Event")
        data = json.loads(payload)
        
        # Route to appropriate handler
        if event_type == "pull_request":
            return await self._handle_pr_event(data)
        
        return {"status": "ignored", "event_type": event_type}
    
    def _verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    async def _handle_pr_event(self, data: dict):
        """Handle pull request events"""
        action = data.get("action")
        
        if action in ["opened", "synchronize", "reopened"]:
            # Trigger PR analysis
            await self.pr_analyzer.analyze_pr_async(data)
            return {"status": "processing", "action": action}
        
        return {"status": "ignored", "action": action}
```

### 3.2 PR Analyzer Implementation

```python
# src/pr_analyzer.py
import os
import asyncio
from github import Github
from openai import AsyncOpenAI
from .auth import GitHubAuth
from .comment_generator import CommentGenerator

class PRAnalyzer:
    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.github_auth = GitHubAuth()
        self.comment_generator = CommentGenerator()
        
    async def analyze_pr_async(self, webhook_data: dict):
        """Analyze PR in background task"""
        # This would be called as a separate Modal function
        pr_data = self._extract_pr_data(webhook_data)
        
        # Get GitHub client for this installation
        github_client = await self.github_auth.get_installation_client(
            pr_data["installation_id"]
        )
        
        # Fetch PR details and diff
        pr_details = await self._fetch_pr_details(github_client, pr_data)
        
        # Analyze code changes
        review_comments = await self._analyze_code_changes(pr_details)
        
        # Post review comments
        await self.comment_generator.post_review(
            github_client, pr_data, review_comments
        )
    
    def _extract_pr_data(self, webhook_data: dict) -> dict:
        """Extract relevant PR data from webhook"""
        pr = webhook_data["pull_request"]
        return {
            "installation_id": webhook_data["installation"]["id"],
            "repo_owner": webhook_data["repository"]["owner"]["login"],
            "repo_name": webhook_data["repository"]["name"],
            "pr_number": pr["number"],
            "pr_id": pr["id"],
            "head_sha": pr["head"]["sha"],
            "base_sha": pr["base"]["sha"]
        }
    
    async def _fetch_pr_details(self, github_client: Github, pr_data: dict):
        """Fetch PR diff and metadata"""
        repo = github_client.get_repo(f"{pr_data['repo_owner']}/{pr_data['repo_name']}")
        pr = repo.get_pull(pr_data["pr_number"])
        
        # Get file changes
        files = list(pr.get_files())
        
        return {
            "pr": pr,
            "files": files,
            "title": pr.title,
            "description": pr.body or ""
        }
    
    async def _analyze_code_changes(self, pr_details: dict) -> list:
        """Analyze code changes with AI"""
        review_comments = []
        
        for file in pr_details["files"]:
            if self._should_analyze_file(file.filename):
                comments = await self._analyze_file_changes(file)
                review_comments.extend(comments)
        
        return review_comments
    
    def _should_analyze_file(self, filename: str) -> bool:
        """Determine if file should be analyzed"""
        # Skip binary files, generated code, etc.
        skip_patterns = [
            ".min.", "node_modules/", ".git/", "__pycache__/",
            ".pyc", ".jpg", ".png", ".pdf", ".zip"
        ]
        
        return not any(pattern in filename for pattern in skip_patterns)
    
    async def _analyze_file_changes(self, file) -> list:
        """Analyze individual file changes with AI"""
        if not file.patch:  # No changes to analyze
            return []
        
        prompt = self._build_analysis_prompt(file)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1000
            )
            
            return self._parse_ai_response(
                response.choices[0].message.content, 
                file.filename
            )
        except Exception as e:
            print(f"Error analyzing {file.filename}: {e}")
            return []
    
    def _build_analysis_prompt(self, file) -> str:
        """Build AI analysis prompt for file changes"""
        return f"""
Analyze this code diff for potential issues and improvements:

File: {file.filename}
Changes: {file.additions} additions, {file.deletions} deletions

Diff:
```
{file.patch}
```

Focus on:
1. Code quality and best practices
2. Potential bugs or logic errors  
3. Security vulnerabilities
4. Performance issues
5. Maintainability concerns

Provide specific, actionable feedback. For each issue:
- Reference the specific line number from the diff
- Explain the problem clearly
- Suggest a concrete improvement

Format response as JSON array:
[
  {{
    "line": <line_number>,
    "type": "suggestion|warning|error", 
    "message": "Specific feedback message",
    "suggestion": "Concrete improvement suggestion"
  }}
]

Only return the JSON array, no other text.
"""
    
    def _parse_ai_response(self, response: str, filename: str) -> list:
        """Parse AI response into structured comments"""
        try:
            import json
            comments_data = json.loads(response)
            
            comments = []
            for comment_data in comments_data:
                comments.append({
                    "filename": filename,
                    "line": comment_data.get("line"),
                    "type": comment_data.get("type", "suggestion"),
                    "message": comment_data.get("message", ""),
                    "suggestion": comment_data.get("suggestion", "")
                })
            
            return comments
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing AI response: {e}")
            return []
```

### 3.3 Authentication Implementation

```python
# src/auth.py
import os
import time
import jwt
from github import Github, GithubIntegration, Auth

class GitHubAuth:
    def __init__(self):
        self.app_id = os.getenv("GITHUB_APP_ID")
        self.private_key = os.getenv("GITHUB_PRIVATE_KEY")
    
    def get_jwt_token(self) -> str:
        """Generate JWT token for GitHub App authentication"""
        payload = {
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,  # 10 minutes
            "iss": self.app_id
        }
        
        return jwt.encode(payload, self.private_key, algorithm="RS256")
    
    async def get_installation_client(self, installation_id: int) -> Github:
        """Get GitHub client for specific installation"""
        jwt_token = self.get_jwt_token()
        auth = Auth.Token(jwt_token)
        
        gi = GithubIntegration(auth=auth)
        access_token = gi.get_access_token(installation_id)
        
        return Github(access_token.token)
```

### 3.4 Comment Generator Implementation

```python
# src/comment_generator.py
from github import Github

class CommentGenerator:
    async def post_review(self, github_client: Github, pr_data: dict, comments: list):
        """Post review comments to GitHub PR"""
        if not comments:
            return
        
        repo = github_client.get_repo(f"{pr_data['repo_owner']}/{pr_data['repo_name']}")
        pr = repo.get_pull(pr_data["pr_number"])
        
        # Group comments by file
        file_comments = {}
        for comment in comments:
            filename = comment["filename"]
            if filename not in file_comments:
                file_comments[filename] = []
            file_comments[filename].append(comment)
        
        # Post review with all comments
        review_body = self._generate_review_summary(comments)
        
        pr_review_comments = []
        for filename, file_comment_list in file_comments.items():
            for comment in file_comment_list:
                pr_review_comments.append({
                    "path": filename,
                    "line": comment["line"],
                    "body": self._format_comment(comment)
                })
        
        # Create review
        pr.create_review(
            body=review_body,
            event="COMMENT",
            comments=pr_review_comments
        )
    
    def _generate_review_summary(self, comments: list) -> str:
        """Generate summary for the review"""
        total_comments = len(comments)
        
        if total_comments == 0:
            return "✅ No issues found in this PR!"
        
        issues_by_type = {}
        for comment in comments:
            comment_type = comment.get("type", "suggestion")
            issues_by_type[comment_type] = issues_by_type.get(comment_type, 0) + 1
        
        summary = f"🤖 **BoxedBot Review Summary**\n\n"
        summary += f"Found {total_comments} potential improvements:\n"
        
        for issue_type, count in issues_by_type.items():
            emoji = {"error": "🚨", "warning": "⚠️", "suggestion": "💡"}.get(issue_type, "📝")
            summary += f"- {emoji} {count} {issue_type}(s)\n"
        
        summary += "\nPlease review the specific comments below."
        return summary
    
    def _format_comment(self, comment: dict) -> str:
        """Format individual comment for GitHub"""
        emoji = {"error": "🚨", "warning": "⚠️", "suggestion": "💡"}.get(comment["type"], "📝")
        
        formatted = f"{emoji} **{comment['type'].title()}**: {comment['message']}"
        
        if comment.get("suggestion"):
            formatted += f"\n\n**Suggestion**: {comment['suggestion']}"
        
        formatted += "\n\n---\n*Generated by BoxedBot*"
        return formatted
```

## Phase 4: Background Processing with Modal

### 4.1 Async PR Analysis Function

```python
# Add to app.py
@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("github-app-secrets"),
        modal.Secret.from_name("openai-secrets")
    ],
    timeout=300,  # 5 minute timeout
    memory=1024   # 1GB memory for AI processing
)
async def analyze_pr_background(pr_data: dict):
    """Background function for PR analysis"""
    from src.pr_analyzer import PRAnalyzer
    
    analyzer = PRAnalyzer()
    await analyzer.analyze_pr_async(pr_data)
    
    return {"status": "completed", "pr_id": pr_data.get("pr_id")}

# Update webhook handler to use background processing
async def _handle_pr_event(self, data: dict):
    """Handle pull request events with background processing"""
    action = data.get("action")
    
    if action in ["opened", "synchronize", "reopened"]:
        # Call background function
        analyze_pr_background.call(data)
        return {"status": "queued", "action": action}
    
    return {"status": "ignored", "action": action}
```

## Phase 5: Configuration Management

### 5.1 Repository Configuration

```python
# src/config_manager.py
import os
import yaml
from typing import Dict, Any
from pydantic import BaseModel

class RepoConfig(BaseModel):
    enabled: bool = True
    file_patterns: list = ["*.py", "*.js", "*.ts", "*.go", "*.rs"]
    exclude_patterns: list = ["node_modules/**", "*.min.js", "__pycache__/**"]
    review_level: str = "standard"  # minimal, standard, strict
    focus_areas: list = ["security", "performance", "style"]
    max_comments_per_pr: int = 20
    ai_model: str = "gpt-4o-mini"

class ConfigManager:
    def __init__(self):
        self.default_config = RepoConfig()
    
    async def get_repo_config(self, github_client, repo_owner: str, repo_name: str) -> RepoConfig:
        """Get configuration for repository"""
        try:
            # Try to load config from repository
            repo = github_client.get_repo(f"{repo_owner}/{repo_name}")
            config_file = repo.get_contents(".boxedbot.yml")
            config_data = yaml.safe_load(config_file.decoded_content)
            
            return RepoConfig(**config_data)
        except Exception:
            # Use default configuration
            return self.default_config
    
    def should_analyze_file(self, filename: str, config: RepoConfig) -> bool:
        """Check if file should be analyzed based on config"""
        import fnmatch
        
        # Check exclude patterns first
        for pattern in config.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False
        
        # Check include patterns
        for pattern in config.file_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        
        return False
```

### 5.2 Example Repository Configuration File

```yaml
# .boxedbot.yml
version: "1.0"

# Enable/disable the bot for this repository
enabled: true

# File patterns to include in review
files:
  include:
    - "src/**/*.py"
    - "tests/**/*.py" 
    - "*.js"
    - "*.ts"
  exclude:
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "*.min.js"
    - "**/migrations/**"

# Review configuration
review:
  level: "standard"  # minimal, standard, strict
  focus_areas:
    - "security"
    - "performance"
    - "style"
    - "maintainability"
  max_comments_per_pr: 15

# AI model configuration
ai:
  model: "gpt-4o-mini"  # or "gpt-4o" for more detailed analysis
  temperature: 0.1
```

## Phase 6: Testing

### 6.1 Unit Tests

```python
# tests/test_webhook.py
import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from src.webhook_handler import WebhookHandler

class TestWebhookHandler:
    def test_verify_signature_valid(self):
        handler = WebhookHandler()
        payload = b'{"test": "data"}'
        secret = "test_secret"
        
        # Create valid signature
        import hmac
        import hashlib
        signature = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': secret}):
            assert handler._verify_signature(payload, signature)
    
    def test_verify_signature_invalid(self):
        handler = WebhookHandler()
        payload = b'{"test": "data"}'
        secret = "test_secret"
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': secret}):
            assert not handler._verify_signature(payload, "invalid_signature")

# tests/test_analyzer.py
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.pr_analyzer import PRAnalyzer

class TestPRAnalyzer:
    @pytest.mark.asyncio
    async def test_should_analyze_file(self):
        analyzer = PRAnalyzer()
        
        assert analyzer._should_analyze_file("src/main.py")
        assert analyzer._should_analyze_file("app.js")
        assert not analyzer._should_analyze_file("node_modules/package.js")
        assert not analyzer._should_analyze_file("image.png")
    
    @pytest.mark.asyncio
    async def test_parse_ai_response(self):
        analyzer = PRAnalyzer()
        
        response = '[{"line": 10, "type": "suggestion", "message": "Test message"}]'
        comments = analyzer._parse_ai_response(response, "test.py")
        
        assert len(comments) == 1
        assert comments[0]["filename"] == "test.py"
        assert comments[0]["line"] == 10
```

### 6.2 Integration Tests

```python
# tests/test_integration.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

@pytest.fixture
def client():
    from app import web_app
    return TestClient(web_app)

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@patch('src.webhook_handler.WebhookHandler.process_webhook')
def test_github_webhook_endpoint(mock_process, client):
    mock_process.return_value = {"status": "processed"}
    
    payload = {"action": "opened", "pull_request": {"id": 123}}
    response = client.post(
        "/webhooks/github",
        json=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "test_signature"
        }
    )
    
    assert response.status_code == 200
```

### 6.3 Running Tests

```bash
# Install testing dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/ -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=src --cov-report=html
```

## Phase 7: Deployment

### 7.1 Development Deployment

```bash
# Serve locally for development
modal serve app.py

# This will output:
# ✓ App deployed locally: https://username--boxedbot-dev.modal.run
```

### 7.2 Production Deployment

```bash
# Deploy to production
modal deploy app.py

# Update GitHub App webhook URL to:
# https://username--boxedbot.modal.run/webhooks/github
```

### 7.3 Environment Management

Create separate environments for development and production:

```python
# app.py - Environment-specific configuration
import os

environment = os.getenv("ENVIRONMENT", "dev")

if environment == "production":
    app_name = "boxedbot"
    secrets = [
        modal.Secret.from_name("github-app-prod"),
        modal.Secret.from_name("openai-prod")
    ]
else:
    app_name = "boxedbot-dev"
    secrets = [
        modal.Secret.from_name("github-app-dev"),
        modal.Secret.from_name("openai-dev")
    ]

app = modal.App(app_name)
```

## Phase 8: Monitoring & Maintenance

### 8.1 Logging Setup

```python
# src/logger.py
import logging
import os
from modal import Secret

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("boxedbot")
    return logger

# Usage in other modules
from src.logger import setup_logging
logger = setup_logging()

logger.info(f"Processing PR {pr_id} for repo {repo_name}")
logger.error(f"Failed to analyze PR {pr_id}: {error}")
```

### 8.2 Error Handling

```python
# src/error_handler.py
import traceback
from typing import Any, Dict

async def handle_error(error: Exception, context: Dict[str, Any]):
    """Centralized error handling"""
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "context": context
    }
    
    # Log error
    logger.error(f"BoxedBot error: {error_data}")
    
    # Could send to external monitoring service
    # await send_to_monitoring_service(error_data)
```

### 8.3 Performance Monitoring

```python
# src/metrics.py
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def track_operation_time(operation_name: str):
    """Track operation timing"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation_name} completed in {duration:.2f}s")
```

## Troubleshooting

### Common Issues

1. **Webhook Signature Verification Fails**
   - Check webhook secret matches in GitHub App and Modal secrets
   - Ensure secret is properly encoded

2. **GitHub API Rate Limiting**
   - Implement exponential backoff
   - Use conditional requests where possible
   - Monitor rate limit headers

3. **OpenAI API Timeouts**
   - Implement retry logic with exponential backoff
   - Use shorter prompts for faster responses
   - Consider GPT-4o-mini for cost and speed

4. **Modal Function Timeouts**
   - Increase timeout for AI processing functions
   - Break large PRs into smaller analysis chunks
   - Use background processing for long operations

### Debugging Tips

```bash
# View Modal logs
modal logs boxedbot

# Stream logs in real-time
modal logs boxedbot --follow

# Check function status
modal app status boxedbot
```

## Next Steps

After completing the basic implementation:

1. **Add Configuration UI**: Build a web interface for repository configuration
2. **Enhanced AI Prompts**: Develop specialized prompts for different languages/frameworks
3. **Analytics Dashboard**: Track usage metrics and review effectiveness
4. **Custom Rules**: Allow teams to define custom review criteria
5. **Integration Tests**: Set up automated testing pipeline
6. **Performance Optimization**: Implement caching and batch processing
7. **Security Hardening**: Add additional security measures and auditing

This implementation guide provides a solid foundation for building BoxedBot with Modal.com and FastAPI, following best practices for security, scalability, and maintainability.