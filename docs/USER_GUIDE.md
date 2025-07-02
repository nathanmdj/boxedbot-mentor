# BoxedBot User Guide

## Overview

BoxedBot is an AI-powered GitHub bot that automatically reviews your pull requests, providing intelligent feedback on code quality, security, performance, and best practices. This guide will help you get started with BoxedBot and make the most of its features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Using BoxedBot](#using-boxedbot)
5. [Understanding Reviews](#understanding-reviews)
6. [Repository Settings](#repository-settings)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [FAQ](#faq)

## Getting Started

### What BoxedBot Does

BoxedBot automatically:
- 🔍 Analyzes pull requests when they're opened or updated
- 💡 Provides intelligent code suggestions and improvements
- 🔒 Identifies potential security vulnerabilities
- ⚡ Highlights performance issues
- 📝 Ensures code follows best practices
- 🎯 Focuses on areas most relevant to your project

### What BoxedBot Doesn't Do

BoxedBot does not:
- Replace human code reviews (it's a complement, not a replacement)
- Automatically merge or approve pull requests
- Make changes to your code
- Access your code beyond the PR diff
- Store your code or sensitive information

## Installation

### Step 1: Install the GitHub App

1. **Visit the GitHub Marketplace**: Go to [GitHub Marketplace](https://github.com/marketplace) and search for "BoxedBot"
2. **Install the App**: Click "Install" and choose the repositories you want to enable
3. **Configure Permissions**: BoxedBot needs read access to your repositories and write access to post PR comments

### Step 2: Choose Installation Scope

**Option A: Install on All Repositories**
- BoxedBot will be available on all current and future repositories
- Recommended for organizations that want consistent code review

**Option B: Install on Selected Repositories**
- Choose specific repositories to enable BoxedBot
- Recommended for trying out the bot or selective usage

### Step 3: Verify Installation

After installation, you should see:
- BoxedBot listed in your repository's "Settings" → "Integrations"
- A welcome comment on your next pull request
- BoxedBot appearing in your organization's installed apps

## Configuration

### Basic Configuration

BoxedBot works out of the box with sensible defaults, but you can customize its behavior for each repository.

### Repository Configuration File

Create a `.boxedbot.yml` file in your repository root to customize BoxedBot's behavior:

```yaml
# .boxedbot.yml
version: "1.0"

# Enable/disable BoxedBot for this repository
enabled: true

# File patterns to review
files:
  include:
    - "src/**/*.py"
    - "src/**/*.js"
    - "src/**/*.ts"
    - "*.go"
    - "*.rs"
  exclude:
    - "**/node_modules/**"
    - "**/__pycache__/**"
    - "*.min.js"
    - "**/dist/**"
    - "**/build/**"

# Review settings
review:
  # Review intensity: minimal, standard, strict
  level: "standard"
  
  # Focus areas for review
  focus_areas:
    - "security"      # Security vulnerabilities
    - "performance"   # Performance issues
    - "style"         # Code style and formatting
    - "maintainability" # Code maintainability
    - "testing"       # Test coverage and quality
  
  # Maximum comments per PR (prevents spam)
  max_comments_per_pr: 20
  
  # Skip reviews for draft PRs
  skip_draft_prs: true

# AI model configuration
ai:
  # Model to use: gpt-4o-mini (faster, cheaper) or gpt-4o (more detailed)
  model: "gpt-4o-mini"
  
  # Response creativity (0.0 = very focused, 1.0 = creative)
  temperature: 0.1

# Custom rules (optional)
rules:
  # Require security review for certain file changes
  security_review:
    files: ["**/auth/**", "**/security/**", "**/*auth*"]
    required: true
  
  # Skip style comments for certain directories
  skip_style_review:
    files: ["**/migrations/**", "**/generated/**"]
```

### Configuration Options Explained

#### Review Levels

**Minimal**:
- Only critical security issues and major bugs
- Fewer than 5 comments per PR typically
- Best for: Mature codebases, experienced teams

**Standard** (Default):
- Balanced approach with security, performance, and maintainability
- 5-15 comments per PR typically
- Best for: Most teams and projects

**Strict**:
- Comprehensive review including style, documentation, and minor issues
- 10-25 comments per PR typically
- Best for: New projects, learning environments, critical systems

#### Focus Areas

- **Security**: SQL injection, XSS, authentication issues, secrets in code
- **Performance**: Inefficient algorithms, memory leaks, database query issues
- **Style**: Code formatting, naming conventions, code organization
- **Maintainability**: Code complexity, documentation, error handling
- **Testing**: Test coverage, test quality, missing test cases

## Using BoxedBot

### How Reviews Work

1. **Automatic Trigger**: BoxedBot analyzes PRs when they're:
   - Opened
   - Updated with new commits
   - Reopened after being closed

2. **Analysis Process**:
   - Fetches the PR diff
   - Analyzes changed files based on configuration
   - Generates review comments using AI
   - Posts structured feedback

3. **Review Timeline**:
   - Initial analysis: 30 seconds - 2 minutes
   - Complex PRs: 2-5 minutes
   - Large PRs: May be split into multiple reviews

### Reading BoxedBot Reviews

BoxedBot provides three types of feedback:

#### 🚨 Critical Issues (Errors)
```
🚨 **Security Vulnerability**: Potential SQL injection vulnerability detected

This query concatenates user input directly into SQL without parameterization.

**Suggestion**: Use parameterized queries or an ORM to prevent SQL injection:
```python
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```
```

#### ⚠️ Important Issues (Warnings)
```
⚠️ **Performance**: Inefficient database query in loop

This code executes a database query for each iteration, causing N+1 query problem.

**Suggestion**: Use a single query with JOIN or prefetch related data:
```python
users = User.objects.select_related('profile').all()
```
```

#### 💡 Suggestions (Improvements)
```
💡 **Code Style**: Consider using more descriptive variable name

Variable name 'x' is not descriptive of its purpose.

**Suggestion**: Use a more descriptive name like 'user_count' or 'total_items'
```

### Interacting with BoxedBot

#### Resolving Comments

1. **Fix the Issue**: Make the suggested changes to your code
2. **Respond to BoxedBot**: Reply to the comment explaining your changes
3. **Mark as Resolved**: GitHub will automatically resolve the comment thread

#### Dismissing Comments

If you disagree with a suggestion:

1. **Reply with Explanation**: Explain why you're not implementing the suggestion
2. **Use Keywords**: Include "dismiss", "ignore", or "not applicable"
3. **BoxedBot Learning**: This helps improve future reviews

#### Requesting Re-review

After making changes:
- Push new commits to trigger automatic re-analysis
- BoxedBot will update existing comments or add new ones
- Resolved issues won't be re-commented

### Managing Review Scope

#### Temporary Disabling

Add a comment to your PR description:
```
<!-- boxedbot:disable -->
This PR contains generated code, skip review.
```

#### Partial Disabling

Disable specific review types:
```
<!-- boxedbot:disable security,style -->
Skip security and style reviews for this PR.
```

#### File-Specific Disabling

Add comments to specific files:
```python
# boxedbot:disable-file
# This file contains legacy code, skip review
```

## Repository Settings

### Team Configuration

For organizations, configure BoxedBot at different levels:

#### Organization Level
- Default settings for all repositories
- Consistent review standards across teams
- Centralized configuration management

#### Repository Level
- Override organization defaults
- Project-specific review requirements
- Team-specific focus areas

#### Branch Protection Rules

Integrate BoxedBot with branch protection:

1. **Go to Repository Settings** → **Branches**
2. **Add Branch Protection Rule** for your main branch
3. **Enable "Require status checks"**
4. **Add "BoxedBot Review"** as a required check

### Review Templates

Create custom review templates for different PR types:

```yaml
# .boxedbot.yml
templates:
  feature:
    focus_areas: ["security", "performance", "testing"]
    max_comments: 15
    
  bugfix:
    focus_areas: ["security", "testing"]
    max_comments: 10
    
  hotfix:
    focus_areas: ["security"]
    max_comments: 5
```

Use templates by adding labels to your PR:
- `type:feature` → Uses feature template
- `type:bugfix` → Uses bugfix template
- `type:hotfix` → Uses hotfix template

### Integration with CI/CD

BoxedBot can integrate with your CI/CD pipeline:

#### GitHub Actions

```yaml
# .github/workflows/boxedbot.yml
name: BoxedBot Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: Wait for BoxedBot Review
        uses: actions/github-script@v6
        with:
          script: |
            // Wait for BoxedBot to complete review
            // Fail if critical issues found
```

#### Status Checks

BoxedBot can post status checks to PRs:

- ✅ **No Critical Issues**: Review passed
- ⚠️ **Issues Found**: Review completed with suggestions
- ❌ **Critical Issues**: Review failed due to security/critical issues

## Troubleshooting

### Common Issues

#### BoxedBot Not Responding

**Symptoms**: No review comments appear after 5+ minutes

**Solutions**:
1. Check if BoxedBot is installed on the repository
2. Verify the PR contains supported file types
3. Check repository configuration file syntax
4. Look for error messages in the PR timeline

#### Too Many Comments

**Symptoms**: BoxedBot posts excessive comments

**Solutions**:
1. Reduce `max_comments_per_pr` in configuration
2. Change review level from "strict" to "standard"
3. Exclude generated files or directories
4. Focus on specific areas using `focus_areas`

#### Comments Not Relevant

**Symptoms**: BoxedBot suggests inappropriate changes

**Solutions**:
1. Adjust `focus_areas` to match your priorities
2. Use file exclusion patterns for generated code
3. Provide feedback by responding to comments
4. Consider using a different AI model in configuration

#### Performance Issues

**Symptoms**: BoxedBot takes too long to review

**Solutions**:
1. Exclude large generated files
2. Limit review to specific directories
3. Use smaller AI model (gpt-4o-mini vs gpt-4o)
4. Split large PRs into smaller ones

### Getting Help

#### Check Status Page

Visit the BoxedBot status page to check for service issues:
- Current service status
- Recent incidents
- Scheduled maintenance

#### GitHub Issues

Report bugs or request features:
1. Go to the BoxedBot GitHub repository
2. Create a new issue with:
   - Repository name
   - PR number
   - Expected vs actual behavior
   - Configuration file (if relevant)

#### Support Channels

- **Documentation**: Check this guide and API documentation
- **Community**: Join our Discord server for community support
- **Enterprise**: Contact support for enterprise installations

## Best Practices

### Writing PR Descriptions

Help BoxedBot understand your changes:

```markdown
## What this PR does
- Adds user authentication system
- Implements JWT token validation
- Updates database schema for user sessions

## BoxedBot Instructions
Please focus on security and performance for this authentication code.
```

### Responding to Reviews

#### Good Responses
```
Thanks for catching this! I've updated the code to use parameterized queries.
```

```
I disagree with this suggestion because this is a performance-critical path where 
the current approach is intentionally optimized. The readability trade-off is acceptable here.
```

#### Poor Responses
```
Ignore this comment
```

```
This is wrong
```

### Configuring for Your Team

#### New Teams
- Start with "standard" review level
- Enable all focus areas
- Gradually adjust based on team feedback

#### Experienced Teams
- Use "minimal" review level
- Focus on security and performance
- Exclude style comments if you have other tools

#### Learning Environments
- Use "strict" review level
- Enable all focus areas including style
- Use detailed AI model (gpt-4o)

### Optimizing Performance

#### File Patterns
```yaml
files:
  include:
    - "src/**/*.{py,js,ts,go,rs}"
  exclude:
    - "**/node_modules/**"
    - "**/dist/**"
    - "**/*.min.js"
    - "**/migrations/**"
    - "**/vendor/**"
```

#### Focus Areas
```yaml
review:
  focus_areas:
    - "security"      # Always include
    - "performance"   # Critical for production
    - "maintainability" # Good for long-term health
    # Exclude "style" if you have other linting tools
```

## FAQ

### General Questions

**Q: Is BoxedBot free?**
A: BoxedBot offers a free tier with 50 PR reviews per month. Paid plans start at $10/month per repository.

**Q: Does BoxedBot store my code?**
A: No, BoxedBot only analyzes PR diffs and doesn't store any code. All analysis is done in real-time.

**Q: Can BoxedBot work with private repositories?**
A: Yes, BoxedBot works with both public and private repositories.

### Technical Questions

**Q: Which programming languages does BoxedBot support?**
A: BoxedBot supports Python, JavaScript, TypeScript, Go, Rust, Java, C#, and more. Language support is continuously expanding.

**Q: How accurate are BoxedBot's suggestions?**
A: BoxedBot has an ~85% accuracy rate for actionable suggestions. It's designed to have high precision to avoid false positives.

**Q: Can BoxedBot review documentation changes?**
A: Yes, BoxedBot can review markdown files, documentation, and comments for clarity and accuracy.

### Configuration Questions

**Q: Can I have different settings for different branches?**
A: Currently, configuration is per-repository. Branch-specific configuration is planned for future releases.

**Q: How do I exclude generated files?**
A: Use the `exclude` patterns in your configuration file to skip generated files, build artifacts, and vendor directories.

**Q: Can I customize the AI prompts?**
A: Custom prompts are available for enterprise plans. Contact support for advanced customization options.

### Integration Questions

**Q: Does BoxedBot integrate with other tools?**
A: BoxedBot integrates with GitHub branch protection, status checks, and popular CI/CD tools. More integrations are planned.

**Q: Can I use BoxedBot with GitHub Enterprise?**
A: Yes, BoxedBot supports GitHub Enterprise Server and GitHub Enterprise Cloud.

**Q: How does BoxedBot handle large PRs?**
A: Large PRs are analyzed in chunks to ensure thorough review while maintaining performance. Analysis may take longer for very large PRs.

## Getting Support

### Documentation Resources

- **API Documentation**: Detailed API reference for integrations
- **Architecture Guide**: Technical overview of BoxedBot's design
- **Implementation Guide**: Step-by-step setup instructions

### Community Support

- **GitHub Discussions**: Ask questions and share tips
- **Discord Server**: Real-time community support
- **Blog**: Best practices and feature announcements

### Enterprise Support

- **Dedicated Support**: Priority support for enterprise customers
- **Custom Integration**: Help with complex integrations
- **Training**: Team training sessions and workshops

---

*This guide is regularly updated. Check the latest version at [BoxedBot Documentation](https://docs.boxedbot.dev)*