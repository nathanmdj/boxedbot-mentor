"""
Pull Request analysis service
"""

import asyncio
from typing import List, Dict, Any, Optional
from github import Github
from github.Repository import Repository
from github.PullRequest import PullRequest

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import PRAnalysisException, FileProcessingException
from app.services.github_service import GitHubService
from app.services.openai_service import OpenAIService
from app.services.config_service import ConfigService
from app.services.comment_service import CommentService


class PRAnalyzerService(LoggerMixin):
    """Service for analyzing pull requests"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.openai_service = OpenAIService()
        self.config_service = ConfigService()
        self.comment_service = CommentService()
    
    async def analyze_pr_async(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a pull request asynchronously"""
        try:
            # Extract PR information
            installation_id = pr_data["installation_id"]
            owner = pr_data["repo_owner"]
            repo_name = pr_data["repo_name"]
            pr_number = pr_data["pr_number"]
            
            self.log_operation(
                "Starting PR analysis",
                repo=f"{owner}/{repo_name}",
                pr_number=pr_number
            )
            
            # Get GitHub client and repository
            github_client = await self.github_service.get_installation_client(installation_id)
            repository = await self.github_service.get_repository(github_client, owner, repo_name)
            pull_request = await self.github_service.get_pull_request(repository, pr_number)
            
            # Get repository configuration
            config = await self.config_service.get_repo_config(installation_id, owner, repo_name)
            
            # Check if analysis should be skipped
            if not config.enabled:
                self.log_operation("Analysis skipped - disabled", pr_number=pr_number)
                return {"status": "skipped", "reason": "disabled"}
            
            if config.skip_draft_prs and pull_request.draft:
                self.log_operation("Analysis skipped - draft PR", pr_number=pr_number)
                return {"status": "skipped", "reason": "draft"}
            
            # Get PR files and context
            pr_files = await self.github_service.get_pr_files(pull_request)
            pr_context = self._build_pr_context(pull_request, pr_files)
            
            # Filter files to analyze
            files_to_analyze = self._filter_files_for_analysis(pr_files, config)
            
            if not files_to_analyze:
                self.log_operation("No files to analyze", pr_number=pr_number)
                return {"status": "completed", "comments": []}
            
            # Analyze files
            all_comments = await self._analyze_files(files_to_analyze, pr_context, config)
            
            # Limit comments per PR
            limited_comments = self._limit_comments(all_comments, config.max_comments_per_pr)
            
            if limited_comments:
                # Post review comments
                await self.comment_service.post_pr_review(
                    pull_request, 
                    limited_comments, 
                    pr_context
                )
            
            self.log_operation(
                "PR analysis completed",
                repo=f"{owner}/{repo_name}",
                pr_number=pr_number,
                total_comments=len(limited_comments)
            )
            
            return {
                "status": "completed",
                "comments": limited_comments,
                "files_analyzed": len(files_to_analyze),
                "total_files": len(pr_files)
            }
            
        except Exception as e:
            self.log_error("PR analysis", e, pr_number=pr_data.get("pr_number"))
            raise PRAnalysisException(f"Failed to analyze PR: {e}")
    
    def _build_pr_context(self, pull_request: PullRequest, pr_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build context information about the PR"""
        total_additions = sum(f.get("additions", 0) for f in pr_files)
        total_deletions = sum(f.get("deletions", 0) for f in pr_files)
        total_changes = total_additions + total_deletions
        
        return {
            "title": pull_request.title,
            "description": pull_request.body or "",
            "author": pull_request.user.login,
            "total_files": len(pr_files),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "total_changes": total_changes,
            "head_sha": pull_request.head.sha,
            "base_sha": pull_request.base.sha,
            "branch": pull_request.head.ref,
            "base_branch": pull_request.base.ref
        }
    
    def _filter_files_for_analysis(
        self, 
        pr_files: List[Dict[str, Any]], 
        config: Any
    ) -> List[Dict[str, Any]]:
        """Filter files that should be analyzed"""
        files_to_analyze = []
        
        for file_data in pr_files:
            filename = file_data["filename"]
            
            # Skip if file is deleted
            if file_data["status"] == "removed":
                continue
            
            # Skip if no patch (binary files, etc.)
            if not file_data.get("patch"):
                continue
            
            # Skip large files
            if file_data.get("changes", 0) > settings.MAX_FILE_SIZE_KB * 10:  # Rough estimate
                self.logger.debug(f"Skipping large file: {filename}")
                continue
            
            # Check if file should be analyzed based on config
            if self.config_service.should_analyze_file(filename, config):
                files_to_analyze.append(file_data)
            else:
                self.logger.debug(f"Skipping file: {filename}")
        
        return files_to_analyze
    
    async def _analyze_files(
        self,
        files_to_analyze: List[Dict[str, Any]],
        pr_context: Dict[str, Any],
        config: Any
    ) -> List[Dict[str, Any]]:
        """Analyze multiple files concurrently"""
        all_comments = []
        
        # Analyze files in batches to avoid overwhelming the API
        batch_size = 3
        for i in range(0, len(files_to_analyze), batch_size):
            batch = files_to_analyze[i:i + batch_size]
            
            # Create analysis tasks for this batch
            tasks = []
            for file_data in batch:
                task = self._analyze_single_file(file_data, pr_context, config)
                tasks.append(task)
            
            # Wait for batch to complete
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f"File analysis failed: {result}")
                    continue
                
                if isinstance(result, list):
                    all_comments.extend(result)
            
            # Small delay between batches
            if i + batch_size < len(files_to_analyze):
                await asyncio.sleep(1)
        
        return all_comments
    
    async def _analyze_single_file(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
        config: Any
    ) -> List[Dict[str, Any]]:
        """Analyze a single file"""
        try:
            filename = file_data["filename"]
            
            # Get focus areas for this file
            focus_areas = self.config_service.get_focus_areas_for_file(filename, config)
            
            # Build file-specific config
            file_config = {
                "focus_areas": focus_areas,
                "review_level": config.review_level,
                "ai_model_override": config.ai_model_override
            }
            
            # Analyze with OpenAI
            comments = await self.openai_service.analyze_code_changes(
                file_data, pr_context, file_config
            )
            
            # Add metadata to comments
            for comment in comments:
                comment["filename"] = filename
                comment["file_changes"] = file_data.get("changes", 0)
            
            return comments
            
        except Exception as e:
            self.log_error("Single file analysis", e, filename=file_data["filename"])
            raise FileProcessingException(f"Failed to analyze file: {e}")
    
    def _limit_comments(
        self, 
        comments: List[Dict[str, Any]], 
        max_comments: int
    ) -> List[Dict[str, Any]]:
        """Limit and prioritize comments based on risk level"""
        if not comments:
            return comments
        
        # Determine risk level based on comment types and categories
        has_high_risk = any(
            c.get("type") == "error" or 
            c.get("category") == "security" or
            "bug" in c.get("message", "").lower() or
            "error" in c.get("message", "").lower() or
            "vulnerability" in c.get("message", "").lower()
            for c in comments
        )
        
        # Set comment limit based on risk level
        if has_high_risk:
            effective_max = 10  # High risk: allow up to 10 comments
            risk_level = "high"
        else:
            effective_max = 5   # Low risk: limit to 5 comments
            risk_level = "low"
        
        # Don't exceed the configured maximum
        effective_max = min(effective_max, max_comments)
        
        if len(comments) <= effective_max:
            self.logger.info(
                f"All {len(comments)} comments included (risk: {risk_level}, limit: {effective_max})"
            )
            return comments
        
        # Sort comments by priority (errors > warnings > suggestions)
        priority_order = {"error": 0, "warning": 1, "suggestion": 2}
        
        sorted_comments = sorted(
            comments,
            key=lambda c: (
                priority_order.get(c.get("type", "suggestion"), 3),
                c.get("category") != "security",  # Prioritize security (False sorts before True)
                "bug" not in c.get("message", "").lower(),  # Prioritize bug-related comments
                "error" not in c.get("message", "").lower(),  # Prioritize error-related comments
                -c.get("file_changes", 0)  # Prioritize files with more changes
            )
        )
        
        limited = sorted_comments[:effective_max]
        
        self.logger.info(
            f"Limited comments from {len(comments)} to {len(limited)} "
            f"(risk: {risk_level}, limit: {effective_max})"
        )
        
        return limited
    
    def calculate_pr_size(self, pr_files: List[Dict[str, Any]]) -> int:
        """Calculate PR size based on total changes"""
        return sum(f.get("changes", 0) for f in pr_files)