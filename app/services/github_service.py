"""
GitHub API service for authentication and repository operations
"""

import os
import time
import jwt
from typing import Optional, List, Dict, Any
from github import Github, GithubIntegration, Auth
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.PullRequestComment import PullRequestComment

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import GitHubAPIException, AuthenticationException


class GitHubService(LoggerMixin):
    """Service for GitHub API operations"""
    
    def __init__(self):
        self.app_id = settings.GITHUB_APP_ID
        self.private_key = settings.GITHUB_PRIVATE_KEY
        self.webhook_secret = settings.GITHUB_WEBHOOK_SECRET
        
        if not all([self.app_id, self.private_key]):
            raise AuthenticationException("GitHub App credentials not configured")
    
    def get_jwt_token(self) -> str:
        """Generate JWT token for GitHub App authentication"""
        try:
            payload = {
                "iat": int(time.time()),
                "exp": int(time.time()) + 600,  # 10 minutes
                "iss": self.app_id
            }
            
            token = jwt.encode(payload, self.private_key, algorithm="RS256")
            self.logger.debug("Generated JWT token for GitHub App")
            return token
            
        except Exception as e:
            self.log_error("JWT token generation", e)
            raise AuthenticationException(f"Failed to generate JWT token: {e}")
    
    async def get_installation_client(self, installation_id: int) -> Github:
        """Get GitHub client for specific installation"""
        try:
            # Use AppAuth for GithubIntegration
            app_auth = Auth.AppAuth(self.app_id, self.private_key)
            gi = GithubIntegration(auth=app_auth)
            
            # Get installation access token
            access_token = gi.get_access_token(installation_id)
            
            # Create client with installation token
            client = Github(access_token.token, timeout=settings.GITHUB_API_TIMEOUT)
            
            self.log_operation("GitHub client created", installation_id=installation_id)
            return client
            
        except Exception as e:
            self.log_error("GitHub client creation", e, installation_id=installation_id)
            raise GitHubAPIException(f"Failed to create GitHub client: {e}")
    
    async def get_repository(
        self, 
        github_client: Github, 
        owner: str, 
        repo_name: str
    ) -> Repository:
        """Get repository object"""
        try:
            repo = github_client.get_repo(f"{owner}/{repo_name}")
            self.log_operation("Repository fetched", repo=f"{owner}/{repo_name}")
            return repo
            
        except Exception as e:
            self.log_error("Repository fetch", e, repo=f"{owner}/{repo_name}")
            raise GitHubAPIException(f"Failed to fetch repository: {e}")
    
    async def get_pull_request(
        self, 
        repository: Repository, 
        pr_number: int
    ) -> PullRequest:
        """Get pull request object"""
        try:
            pr = repository.get_pull(pr_number)
            self.log_operation("Pull request fetched", pr_number=pr_number)
            return pr
            
        except Exception as e:
            self.log_error("Pull request fetch", e, pr_number=pr_number)
            raise GitHubAPIException(f"Failed to fetch pull request: {e}")
    
    async def get_pr_files(self, pull_request: PullRequest) -> List[Dict[str, Any]]:
        """Get files changed in pull request"""
        try:
            files = []
            for file in pull_request.get_files():
                file_data = {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "patch": file.patch,
                    "raw_url": file.raw_url,
                    "blob_url": file.blob_url
                }
                files.append(file_data)
            
            self.log_operation(
                "PR files fetched", 
                pr_number=pull_request.number,
                file_count=len(files)
            )
            return files
            
        except Exception as e:
            self.log_error("PR files fetch", e, pr_number=pull_request.number)
            raise GitHubAPIException(f"Failed to fetch PR files: {e}")
    
    async def create_review_comment(
        self,
        pull_request: PullRequest,
        comment_data: Dict[str, Any]
    ) -> PullRequestComment:
        """Create a review comment on a pull request"""
        try:
            comment = pull_request.create_review_comment(
                body=comment_data["body"],
                commit_id=comment_data["commit_id"],
                path=comment_data["path"],
                line=comment_data.get("line"),
                start_line=comment_data.get("start_line"),
                start_side=comment_data.get("start_side", "RIGHT"),
                side=comment_data.get("side", "RIGHT")
            )
            
            self.log_operation(
                "Review comment created",
                pr_number=pull_request.number,
                path=comment_data["path"],
                line=comment_data.get("line")
            )
            return comment
            
        except Exception as e:
            self.log_error(
                "Review comment creation", 
                e, 
                pr_number=pull_request.number,
                path=comment_data["path"]
            )
            raise GitHubAPIException(f"Failed to create review comment: {e}")
    
    async def create_pr_review(
        self,
        pull_request: PullRequest,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """Create a pull request review"""
        try:
            review_comments = []
            if comments:
                for comment in comments:
                    if comment.get("line") and comment.get("path"):
                        review_comments.append({
                            "path": comment["path"],
                            "line": comment["line"],
                            "body": comment["body"]
                        })
            
            review = pull_request.create_review(
                body=body,
                event=event,
                comments=review_comments if review_comments else None
            )
            
            self.log_operation(
                "PR review created",
                pr_number=pull_request.number,
                event=event,
                comment_count=len(review_comments)
            )
            return review
            
        except Exception as e:
            self.log_error("PR review creation", e, pr_number=pull_request.number)
            raise GitHubAPIException(f"Failed to create PR review: {e}")
    
    async def get_repository_content(
        self,
        repository: Repository,
        path: str,
        ref: Optional[str] = None
    ) -> str:
        """Get content of a file in repository"""
        try:
            # Don't pass ref if it's None
            if ref is not None:
                content = repository.get_contents(path, ref=ref)
            else:
                content = repository.get_contents(path)
                
            if hasattr(content, 'decoded_content'):
                return content.decoded_content.decode('utf-8')
            return ""
            
        except Exception as e:
            # 404 errors are expected for missing config files
            if "404" in str(e) and path in [".boxedbot.yml", ".boxedbot.yaml"]:
                self.logger.debug(f"Config file {path} not found (this is normal)")
            else:
                self.log_error("Repository content fetch", e, path=path)
            # Don't raise exception for missing files
            return ""
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        try:
            import hmac
            import hashlib
            
            if not signature or not self.webhook_secret:
                return False
            
            expected = hmac.new(
                self.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(f"sha256={expected}", signature)
            
        except Exception as e:
            self.log_error("Webhook signature verification", e)
            return False