"""
Comment service for posting PR reviews and managing comments
"""

from typing import List, Dict, Any, Optional
from github.PullRequest import PullRequest

from app.core.logging import LoggerMixin
from app.core.exceptions import GitHubAPIException
from app.services.github_service import GitHubService
from app.services.openai_service import OpenAIService


class CommentService(LoggerMixin):
    """Service for managing PR comments and reviews"""
    
    def __init__(self):
        self.github_service = GitHubService()
        self.openai_service = OpenAIService()
    
    async def post_pr_review(
        self,
        pull_request: PullRequest,
        comments: List[Dict[str, Any]],
        pr_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post a complete review to a pull request"""
        try:
            if not comments:
                return {"status": "skipped", "reason": "no_comments"}
            
            # Generate review summary
            review_summary = await self.openai_service.generate_review_summary(
                comments, pr_context
            )
            
            # Group comments by file and prepare for GitHub API
            review_comments = self._prepare_review_comments(comments, pull_request)
            
            # Create the review
            review = await self.github_service.create_pr_review(
                pull_request=pull_request,
                body=review_summary,
                event="COMMENT",
                comments=review_comments
            )
            
            self.log_operation(
                "PR review posted",
                pr_number=pull_request.number,
                comment_count=len(review_comments),
                review_id=review.id
            )
            
            return {
                "status": "posted",
                "review_id": review.id,
                "comments_posted": len(review_comments),
                "summary": review_summary
            }
            
        except Exception as e:
            self.log_error("PR review posting", e, pr_number=pull_request.number)
            raise GitHubAPIException(f"Failed to post PR review: {e}")
    
    def _prepare_review_comments(
        self,
        comments: List[Dict[str, Any]],
        pull_request: PullRequest
    ) -> List[Dict[str, Any]]:
        """Prepare comments for GitHub API format"""
        review_comments = []
        
        for comment in comments:
            if not self._is_valid_comment(comment):
                self.logger.warning(f"Invalid comment format: {comment}")
                continue
            
            # Format comment body
            comment_body = self._format_comment_body(comment)
            
            # Try to map line number to GitHub's format
            github_line = self._map_line_number(comment, pull_request)
            
            if github_line is None:
                self.logger.warning(
                    f"Could not map line number for comment: {comment.get('line')} "
                    f"in file {comment.get('filename')}"
                )
                continue
            
            review_comment = {
                "path": comment["filename"],
                "line": github_line,
                "body": comment_body
            }
            
            review_comments.append(review_comment)
        
        return review_comments
    
    def _is_valid_comment(self, comment: Dict[str, Any]) -> bool:
        """Validate comment has required fields"""
        required_fields = ["filename", "line", "type", "message"]
        return all(field in comment and comment[field] for field in required_fields)
    
    def _format_comment_body(self, comment: Dict[str, Any]) -> str:
        """Format comment for display in GitHub"""
        # Choose emoji based on comment type
        type_emojis = {
            "error": "🚨",
            "warning": "⚠️", 
            "suggestion": "💡"
        }
        
        category_emojis = {
            "security": "🔒",
            "performance": "⚡",
            "maintainability": "🔧",
            "style": "🎨",
            "testing": "🧪"
        }
        
        comment_type = comment.get("type", "suggestion")
        category = comment.get("category", "general")
        
        type_emoji = type_emojis.get(comment_type, "📝")
        category_emoji = category_emojis.get(category, "")
        
        # Build comment body
        header = f"{type_emoji} **{comment_type.title()}**"
        if category != "general":
            header += f" {category_emoji} *({category.title()})*"
        
        body = f"{header}\n\n{comment['message']}"
        
        # Add suggestion if provided
        if comment.get("suggestion"):
            body += f"\n\n**💡 Suggestion:**\n{comment['suggestion']}"
        
        # Add code example if provided
        if comment.get("code_example"):
            body += f"\n\n**📝 Example:**\n```\n{comment['code_example']}\n```"
        
        # Add footer
        body += "\n\n---\n*🤖 Generated by BoxedBot*"
        
        return body
    
    def _map_line_number(
        self,
        comment: Dict[str, Any],
        pull_request: PullRequest
    ) -> Optional[int]:
        """Map diff line number to GitHub line number"""
        try:
            # For now, return the line number as-is
            # In a more sophisticated implementation, we would:
            # 1. Parse the diff to understand line mappings
            # 2. Map diff line numbers to actual file line numbers
            # 3. Handle context lines and line number offsets
            
            line_number = comment.get("line")
            if isinstance(line_number, int) and line_number > 0:
                return line_number
            
            return None
            
        except Exception as e:
            self.log_error("Line number mapping", e, comment=comment)
            return None
    
    async def post_simple_comment(
        self,
        pull_request: PullRequest,
        message: str
    ) -> Dict[str, Any]:
        """Post a simple comment to a PR"""
        try:
            comment = pull_request.create_issue_comment(message)
            
            self.log_operation(
                "Simple comment posted",
                pr_number=pull_request.number,
                comment_id=comment.id
            )
            
            return {
                "status": "posted",
                "comment_id": comment.id,
                "message": message
            }
            
        except Exception as e:
            self.log_error("Simple comment posting", e, pr_number=pull_request.number)
            raise GitHubAPIException(f"Failed to post comment: {e}")
    
    async def post_error_comment(
        self,
        pull_request: PullRequest,
        error_message: str
    ) -> Dict[str, Any]:
        """Post an error comment when analysis fails"""
        message = f"""
🚨 **BoxedBot Analysis Failed**

I encountered an error while analyzing this pull request:

```
{error_message}
```

Please check the PR for any unusual changes or contact support if this issue persists.

---
*🤖 Generated by BoxedBot*
"""
        
        return await self.post_simple_comment(pull_request, message)
    
    async def post_skipped_comment(
        self,
        pull_request: PullRequest,
        reason: str
    ) -> Dict[str, Any]:
        """Post a comment when analysis is skipped"""
        reason_messages = {
            "disabled": "BoxedBot is disabled for this repository.",
            "draft": "BoxedBot skips draft pull requests by default.",
            "no_files": "No supported files found for analysis.",
            "too_large": "Pull request is too large for analysis."
        }
        
        reason_text = reason_messages.get(reason, f"Analysis skipped: {reason}")
        
        message = f"""
ℹ️ **BoxedBot Analysis Skipped**

{reason_text}

---
*🤖 Generated by BoxedBot*
"""
        
        return await self.post_simple_comment(pull_request, message)
    
    def format_review_stats(self, comments: List[Dict[str, Any]]) -> str:
        """Format statistics about the review"""
        if not comments:
            return "No issues found! ✨"
        
        # Count by type
        type_counts = {}
        category_counts = {}
        
        for comment in comments:
            comment_type = comment.get("type", "suggestion")
            category = comment.get("category", "general")
            
            type_counts[comment_type] = type_counts.get(comment_type, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Format stats
        stats = []
        
        # Type breakdown
        if type_counts:
            type_stats = []
            for ctype, count in sorted(type_counts.items()):
                type_stats.append(f"{count} {ctype}{'s' if count != 1 else ''}")
            stats.append("**Issues:** " + ", ".join(type_stats))
        
        # Category breakdown
        if category_counts:
            category_stats = []
            for category, count in sorted(category_counts.items()):
                if category != "general":
                    category_stats.append(f"{count} {category}")
            if category_stats:
                stats.append("**Areas:** " + ", ".join(category_stats))
        
        return " | ".join(stats) if stats else "Analysis completed"