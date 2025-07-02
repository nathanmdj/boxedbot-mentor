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
            
            # If no valid inline comments could be created, post a general comment
            if not review_comments:
                self.logger.warning(f"No valid inline comments for PR #{pull_request.number}, posting general comment")
                fallback_message = self._create_fallback_comment(comments, review_summary)
                return await self.post_simple_comment(pull_request, fallback_message)
            
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
            # Try fallback comment on any error
            try:
                review_summary = await self.openai_service.generate_review_summary(comments, pr_context)
                fallback_message = self._create_fallback_comment(comments, review_summary)
                return await self.post_simple_comment(pull_request, fallback_message)
            except:
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
        """Validate line number is valid for GitHub review comment"""
        try:
            filename = comment.get("filename")
            line_number = comment.get("line")
            
            if not filename or not isinstance(line_number, int) or line_number <= 0:
                return None
            
            # Get the file from the PR to access its patch
            pr_files = pull_request.get_files()
            target_file = None
            
            for file in pr_files:
                if file.filename == filename:
                    target_file = file
                    break
            
            if not target_file or not target_file.patch:
                self.logger.warning(f"No patch found for file {filename}")
                return None
            
            # Parse the diff to find valid line numbers
            valid_lines = self._get_valid_diff_lines(target_file.patch)
            
            # Check if the provided line number is valid for GitHub review comments
            if line_number in valid_lines:
                return line_number
            
            # Find the closest valid line (within 5 lines)
            closest_line = self._find_closest_valid_line(line_number, valid_lines, max_distance=5)
            if closest_line:
                self.logger.debug(f"Adjusted line {line_number} to closest valid line {closest_line} in {filename}")
                return closest_line
            
            self.logger.warning(f"Line {line_number} is not valid for GitHub review comment in {filename}")
            return None
            
        except Exception as e:
            self.log_error("Line number validation", e, comment=comment)
            return None
    
    def _get_valid_diff_lines(self, patch: str) -> List[int]:
        """Extract valid line numbers from diff patch"""
        from app.utils.file_utils import DiffParser
        
        parser = DiffParser()
        diff_info = parser.parse_diff_lines(patch)
        
        valid_lines = []
        for line_info in diff_info['added_lines']:
            if line_info['new_line'] > 0:
                valid_lines.append(line_info['new_line'])
        
        # Also include context lines that are part of hunks
        for line_info in diff_info['context_lines']:
            if line_info['new_line'] > 0:
                valid_lines.append(line_info['new_line'])
        
        return sorted(set(valid_lines))
    
    def _find_closest_valid_line(self, target_line: int, valid_lines: List[int], max_distance: int = 5) -> Optional[int]:
        """Find the closest valid line within max_distance"""
        if not valid_lines:
            return None
        
        closest_line = None
        min_distance = float('inf')
        
        for valid_line in valid_lines:
            distance = abs(valid_line - target_line)
            if distance <= max_distance and distance < min_distance:
                min_distance = distance
                closest_line = valid_line
        
        return closest_line
    
    def _create_fallback_comment(self, comments: List[Dict[str, Any]], review_summary: str) -> str:
        """Create a fallback general comment when inline comments can't be placed"""
        message_parts = []
        
        # Add review summary
        message_parts.append(f"🤖 **BoxedBot Code Review**\n\n{review_summary}")
        
        # Group comments by file
        files_comments = {}
        for comment in comments:
            filename = comment.get("filename", "unknown")
            if filename not in files_comments:
                files_comments[filename] = []
            files_comments[filename].append(comment)
        
        # Add detailed findings
        message_parts.append("\n## 📋 Detailed Findings\n")
        
        for filename, file_comments in files_comments.items():
            message_parts.append(f"### 📄 `{filename}`\n")
            
            for i, comment in enumerate(file_comments, 1):
                line = comment.get("line", "")
                comment_type = comment.get("type", "suggestion")
                category = comment.get("category", "general")
                message = comment.get("message", "")
                
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
                
                type_emoji = type_emojis.get(comment_type, "📝")
                category_emoji = category_emojis.get(category, "")
                
                line_info = f" (Line {line})" if line else ""
                category_info = f" *{category_emoji} {category.title()}*" if category != "general" else ""
                
                message_parts.append(f"{i}. {type_emoji} **{comment_type.title()}**{line_info}{category_info}")
                message_parts.append(f"   {message}\n")
        
        # Add footer
        message_parts.append("---\n*🤖 Generated by BoxedBot - Unable to place inline comments due to diff limitations*")
        
        return "\n".join(message_parts)
    
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