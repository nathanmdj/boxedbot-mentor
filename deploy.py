#!/usr/bin/env python3
"""
Deployment script for BoxedBot using Modal
"""

import os
import sys
import subprocess
from pathlib import Path


def check_requirements():
    """Check if required tools are installed"""
    try:
        import modal
        print("✓ Modal is installed")
    except ImportError:
        print("✗ Modal is not installed. Run: pip install modal")
        return False
    
    try:
        result = subprocess.run(["modal", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Modal CLI is available: {result.stdout.strip()}")
        else:
            print("✗ Modal CLI is not working properly")
            return False
    except FileNotFoundError:
        print("✗ Modal CLI not found. Make sure it's in your PATH")
        return False
    
    return True


def check_secrets():
    """Check if required secrets are configured"""
    required_secrets = [
        "github-app-secrets",
        "openai-secrets"
    ]
    
    missing_secrets = []
    
    for secret_name in required_secrets:
        try:
            result = subprocess.run(
                ["modal", "secret", "list"],
                capture_output=True,
                text=True
            )
            if secret_name not in result.stdout:
                missing_secrets.append(secret_name)
        except Exception as e:
            print(f"Error checking secrets: {e}")
            return False
    
    if missing_secrets:
        print("✗ Missing secrets:")
        for secret in missing_secrets:
            print(f"  - {secret}")
        print("\nPlease create secrets using:")
        print("modal secret create github-app-secrets GITHUB_APP_ID=... GITHUB_PRIVATE_KEY=... GITHUB_WEBHOOK_SECRET=...")
        print("modal secret create openai-secrets OPENAI_API_KEY=...")
        return False
    
    print("✓ All required secrets are configured")
    return True


def deploy(environment="production"):
    """Deploy the application to Modal"""
    print(f"Deploying BoxedBot to {environment}...")
    
    # Set environment variable
    os.environ["ENVIRONMENT"] = environment
    
    try:
        if environment == "development":
            # Use modal serve for development
            print("Starting development server...")
            result = subprocess.run(["modal", "serve", "main.py"])
        else:
            # Use modal deploy for production
            print("Deploying to production...")
            result = subprocess.run(["modal", "deploy", "main.py"])
        
        if result.returncode == 0:
            print(f"✓ Successfully deployed to {environment}")
            
            if environment == "production":
                print("\nYour BoxedBot is now live!")
                print("Update your GitHub App webhook URL to:")
                print("https://your-username--boxedbot.modal.run/api/v1/webhooks/github")
            
            return True
        else:
            print(f"✗ Deployment failed with return code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ Deployment error: {e}")
        return False


def main():
    """Main deployment function"""
    print("BoxedBot Deployment Script")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("✗ main.py not found. Make sure you're in the project root directory.")
        sys.exit(1)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check secrets
    if not check_secrets():
        sys.exit(1)
    
    # Get deployment environment
    environment = "production"
    if len(sys.argv) > 1:
        environment = sys.argv[1]
        if environment not in ["development", "production"]:
            print("Invalid environment. Use 'development' or 'production'")
            sys.exit(1)
    
    # Deploy
    if deploy(environment):
        print("\n🎉 Deployment completed successfully!")
        
        if environment == "development":
            print("\nDevelopment server is running. Press Ctrl+C to stop.")
        
    else:
        print("\n❌ Deployment failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()