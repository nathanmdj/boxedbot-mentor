# BoxedBot - AI-Powered PR Reviewer

BoxedBot is an intelligent GitHub bot that automatically reviews your pull requests using AI, providing actionable feedback on code quality, security, performance, and best practices.

## Features

- 🤖 **AI-Powered Analysis**: Uses GPT-4o/4o-mini for intelligent code review
- 🔒 **Security Focus**: Identifies potential security vulnerabilities
- ⚡ **Performance Optimization**: Highlights performance bottlenecks
- 🛠️ **Maintainability**: Suggests improvements for code maintainability
- 📝 **Style Guidelines**: Enforces coding standards and best practices
- ⚙️ **Configurable**: Customizable per repository via `.boxedbot.yml`
- 🚀 **Serverless**: Deployed on Modal.com for automatic scaling
- 💰 **Cost-Effective**: Smart model selection based on PR size

## Quick Start

### Prerequisites

- Python 3.11+
- Modal.com account
- GitHub App credentials
- OpenAI API key

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd boxedbot-code
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   Note: `requirements.txt` is for local development. Production dependencies are defined in `main.py` and automatically installed in Modal containers.

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Configure Modal secrets**:
   ```bash
   modal secret create github-app-secrets \
     GITHUB_APP_ID="your_app_id" \
     GITHUB_PRIVATE_KEY="$(cat private-key.pem)" \
     GITHUB_WEBHOOK_SECRET="your_webhook_secret"
   
   modal secret create openai-secrets \
     OPENAI_API_KEY="sk-your-openai-api-key"
   ```

5. **Deploy to Modal**:
   ```bash
   python deploy.py production
   ```

### Development

For local development:

```bash
python deploy.py development
```

This starts a development server with hot reloading.

## Configuration

Create a `.boxedbot.yml` file in your repository root:

```yaml
version: "1.0"
enabled: true

files:
  include:
    - "src/**/*.py"
    - "src/**/*.js" 
    - "src/**/*.ts"
  exclude:
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "*.min.js"

review:
  level: "standard"  # minimal, standard, strict
  focus_areas:
    - "security"
    - "performance"
    - "maintainability"
  max_comments_per_pr: 20
  skip_draft_prs: true

ai:
  model_override: null  # Force specific model
  temperature: 0.1
```

## Project Structure

```
boxedbot-code/
├── main.py                 # Modal application entry point
├── app/
│   ├── core/              # Core configuration and utilities
│   │   ├── config.py      # Application settings
│   │   ├── logging.py     # Logging configuration
│   │   └── exceptions.py  # Custom exceptions
│   ├── services/          # Business logic services
│   │   ├── github_service.py      # GitHub API integration
│   │   ├── openai_service.py      # OpenAI API integration
│   │   ├── pr_analyzer.py         # PR analysis logic
│   │   ├── comment_service.py     # Comment management
│   │   ├── config_service.py      # Configuration management
│   │   ├── webhook_service.py     # Webhook processing
│   │   └── health_service.py      # Health checks
│   ├── api/               # FastAPI endpoints
│   │   ├── routes.py      # Main router
│   │   └── endpoints/     # Endpoint modules
│   │       ├── webhooks.py    # Webhook endpoints
│   │       ├── health.py      # Health check endpoints
│   │       └── config.py      # Configuration endpoints
│   └── utils/             # Utility functions
│       ├── file_utils.py      # File processing utilities
│       ├── validation.py      # Input validation
│       ├── rate_limiter.py    # Rate limiting
│       └── retry_utils.py     # Retry logic
├── requirements.txt       # Python dependencies
├── deploy.py             # Deployment script
├── .env.example          # Environment variables template
└── README.md            # This file
```

## API Endpoints

### Webhooks
- `POST /api/v1/webhooks/github` - GitHub webhook handler
- `GET /api/v1/webhooks/github/events` - Supported events list

### Health Checks
- `GET /api/v1/health/` - Basic health check
- `GET /api/v1/health/detailed` - Detailed health with dependencies
- `GET /api/v1/health/dependencies` - External dependencies status

### Configuration
- `GET /api/v1/config/{repo_id}` - Get repository configuration
- `POST /api/v1/config/{repo_id}` - Update repository configuration
- `DELETE /api/v1/config/{repo_id}` - Reset to default configuration

## Deployment

### Production Deployment

1. **Configure secrets** in Modal
2. **Run deployment script**:
   ```bash
   python deploy.py production
   ```
3. **Update GitHub App webhook URL** to the deployed endpoint

### Environment Variables

Required environment variables:

- `GITHUB_APP_ID` - Your GitHub App ID
- `GITHUB_PRIVATE_KEY` - GitHub App private key (PEM format)
- `GITHUB_WEBHOOK_SECRET` - Webhook secret for signature verification
- `OPENAI_API_KEY` - OpenAI API key

Optional variables:

- `ENVIRONMENT` - deployment environment (development/production)
- `DEBUG` - enable debug mode
- `OPENAI_MODEL_SMALL` - model for small PRs (default: gpt-4o-mini)
- `OPENAI_MODEL_LARGE` - model for large PRs (default: gpt-4o)

## Usage

1. **Install BoxedBot** on your GitHub repository
2. **Configure** (optional) by adding `.boxedbot.yml` to your repo
3. **Create a PR** - BoxedBot will automatically analyze and comment
4. **Review suggestions** and implement improvements
5. **Respond to comments** if you disagree or need clarification

## Features in Detail

### AI Model Selection

BoxedBot automatically selects the appropriate AI model based on PR size:

- **Small PRs** (< 100 lines): GPT-4o-mini (faster, cost-effective)
- **Medium PRs** (100-500 lines): GPT-4o-mini
- **Large PRs** (> 500 lines): GPT-4o (more comprehensive analysis)

### Review Types

- **🚨 Errors**: Critical issues that should be fixed immediately
- **⚠️ Warnings**: Important issues that may cause problems
- **💡 Suggestions**: Improvements and best practices

### Focus Areas

- **Security**: Vulnerability detection, input validation, authentication issues
- **Performance**: Optimization opportunities, efficiency improvements
- **Maintainability**: Code organization, readability, documentation
- **Style**: Formatting, naming conventions, code standards
- **Testing**: Test coverage, test quality, missing tests

## Monitoring

BoxedBot provides comprehensive monitoring:

- **Health checks** for service and dependency status
- **Metrics** for analysis performance and usage
- **Logging** for debugging and monitoring
- **Rate limiting** to prevent API abuse

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[MIT License](LICENSE)

## Support

- **Documentation**: See the `docs/` directory
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions for questions

---

*Built with ❤️ using Modal.com, FastAPI, and OpenAI*