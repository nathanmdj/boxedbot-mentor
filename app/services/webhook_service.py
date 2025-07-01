"""
Webhook service for handling GitHub webhook events
"""

import json
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import WebhookException, AuthenticationException
from app.services.github_service import GitHubService


class WebhookService(LoggerMixin):
    """Service for processing GitHub webhooks"""
    
    def __init__(self):
        self.github_service = GitHubService()
    
    async def process_webhook(self, request: Request) -> Dict[str, Any]:
        """Process incoming GitHub webhook"""
        try:
            # Get headers
            event_type = request.headers.get("X-GitHub-Event")
            signature = request.headers.get("X-Hub-Signature-256")
            delivery_id = request.headers.get("X-GitHub-Delivery")
            
            if not event_type:
                raise WebhookException("Missing X-GitHub-Event header")
            
            # Get payload
            payload = await request.body()
            
            # Verify signature
            if not self.github_service.verify_webhook_signature(payload, signature):
                self.log_error(
                    "Webhook signature verification failed",
                    Exception("Invalid signature"),
                    event_type=event_type,
                    delivery_id=delivery_id
                )
                raise AuthenticationException("Invalid webhook signature")
            
            # Parse JSON payload
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as e:
                raise WebhookException(f"Invalid JSON payload: {e}")
            
            self.log_operation(
                "Webhook received",
                event_type=event_type,
                delivery_id=delivery_id,
                action=data.get("action")
            )
            
            # Route to appropriate handler
            return await self._route_webhook_event(event_type, data)
            
        except WebhookException:
            raise
        except AuthenticationException:
            raise
        except Exception as e:
            self.log_error("Webhook processing", e)
            raise WebhookException(f"Failed to process webhook: {e}")
    
    async def _route_webhook_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Route webhook event to appropriate handler"""
        
        if event_type == "pull_request":
            return await self._handle_pull_request_event(data)
        elif event_type == "pull_request_review":
            return await self._handle_pull_request_review_event(data)
        elif event_type == "installation_target":
            return await self._handle_installation_target_event(data)
        elif event_type == "ping":
            return await self._handle_ping_event(data)
        else:
            self.logger.info(f"Unsupported event type: {event_type}")
            return {
                "status": "ignored",
                "event_type": event_type,
                "message": "Event type not supported"
            }
    
    async def _handle_pull_request_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pull request webhook events"""
        action = data.get("action")
        
        # Only process certain actions
        if action not in ["opened", "synchronize", "reopened"]:
            return {
                "status": "ignored",
                "action": action,
                "message": f"Action '{action}' not processed"
            }
        
        try:
            # Extract PR data
            pr_data = self._extract_pr_data(data)
            
            # Import here to avoid circular imports
            from main import analyze_pr_background
            
            # Queue background analysis
            analyze_pr_background.spawn(pr_data)
            
            self.log_operation(
                "PR analysis queued",
                repo=f"{pr_data['repo_owner']}/{pr_data['repo_name']}",
                pr_number=pr_data["pr_number"],
                action=action
            )
            
            return {
                "status": "queued",
                "action": action,
                "pr_id": pr_data["pr_id"],
                "pr_number": pr_data["pr_number"],
                "message": "PR analysis queued for processing"
            }
            
        except Exception as e:
            self.log_error("PR event handling", e, action=action)
            raise WebhookException(f"Failed to handle PR event: {e}")
    
    async def _handle_pull_request_review_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pull request review events"""
        action = data.get("action")
        
        # For future features like responding to review comments
        self.logger.info(f"PR review event received: {action}")
        
        return {
            "status": "received",
            "action": action,
            "message": "PR review event logged"
        }
    
    async def _handle_installation_target_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub App installation target events"""
        action = data.get("action")
        installation_id = data.get("installation", {}).get("id")
        account = data.get("installation", {}).get("account", {})
        
        self.log_operation(
            "Installation event",
            action=action,
            installation_id=installation_id,
            account=account.get("login")
        )
        
        if action == "created":
            # New installation
            return {
                "status": "installed",
                "installation_id": installation_id,
                "account": account.get("login"),
                "message": "BoxedBot installed successfully"
            }
        elif action == "deleted":
            # Installation removed
            return {
                "status": "uninstalled",
                "installation_id": installation_id,
                "account": account.get("login"),
                "message": "BoxedBot uninstalled"
            }
        
        return {
            "status": "processed",
            "action": action,
            "installation_id": installation_id
        }
    
    
    async def _handle_ping_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping events"""
        zen = data.get("zen", "GitHub is awesome!")
        
        self.log_operation("Ping event received", zen=zen)
        
        return {
            "status": "pong",
            "message": "BoxedBot is alive and ready!",
            "zen": zen
        }
    
    def _extract_pr_data(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant PR data from webhook payload"""
        try:
            pr = webhook_data["pull_request"]
            repository = webhook_data["repository"]
            installation = webhook_data["installation"]
            
            return {
                "installation_id": installation["id"],
                "repo_owner": repository["owner"]["login"],
                "repo_name": repository["name"],
                "repo_id": repository["id"],
                "pr_number": pr["number"],
                "pr_id": pr["id"],
                "pr_title": pr["title"],
                "pr_body": pr["body"] or "",
                "head_sha": pr["head"]["sha"],
                "base_sha": pr["base"]["sha"],
                "head_ref": pr["head"]["ref"],
                "base_ref": pr["base"]["ref"],
                "author": pr["user"]["login"],
                "draft": pr.get("draft", False),
                "action": webhook_data.get("action"),
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"]
            }
            
        except KeyError as e:
            raise WebhookException(f"Missing required field in webhook data: {e}")
    
    def _validate_webhook_data(self, data: Dict[str, Any], required_fields: list) -> None:
        """Validate that webhook data contains required fields"""
        for field in required_fields:
            if field not in data:
                raise WebhookException(f"Missing required field: {field}")
    
    def get_supported_events(self) -> list:
        """Get list of supported webhook events"""
        return [
            "pull_request",
            "pull_request_review", 
            "installation_target",  # Updated event name
            "ping"
        ]