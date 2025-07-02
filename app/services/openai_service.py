"""
OpenAI API service for code analysis and review generation
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import LoggerMixin
from app.core.exceptions import OpenAIAPIException


class OpenAIService(LoggerMixin):
    """Service for OpenAI API operations"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            organization=settings.OPENAI_ORG_ID,
            timeout=settings.OPENAI_API_TIMEOUT
        )
        
        if not settings.OPENAI_API_KEY:
            raise OpenAIAPIException("OpenAI API key not configured")
    
    def select_model(self, pr_size: int) -> str:
        """Select appropriate AI model based on PR size"""
        if pr_size <= settings.SMALL_PR_THRESHOLD:
            return settings.OPENAI_MODEL_SMALL
        elif pr_size <= settings.MEDIUM_PR_THRESHOLD:
            return settings.OPENAI_MODEL_SMALL  # Still use small for medium PRs
        else:
            return settings.OPENAI_MODEL_LARGE
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def analyze_code_changes(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze code changes in a file"""
        try:
            if not file_data.get("patch"):
                return []
            
            # Select model based on PR size
            pr_size = pr_context.get("total_changes", 0)
            model = self.select_model(pr_size)
            
            # Build analysis prompt
            prompt = self._build_analysis_prompt(file_data, pr_context, config)
            
            self.log_operation(
                "Starting code analysis",
                filename=file_data["filename"],
                model=model,
                pr_size=pr_size
            )
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS
            )
            
            # Parse AI response
            comments = self._parse_ai_response(
                response.choices[0].message.content,
                file_data["filename"]
            )
            
            self.log_operation(
                "Code analysis completed",
                filename=file_data["filename"],
                model=model,
                comment_count=len(comments)
            )
            
            return comments
            
        except Exception as e:
            self.log_error(
                "Code analysis",
                e,
                filename=file_data["filename"],
                model=model if 'model' in locals() else "unknown"
            )
            raise OpenAIAPIException(f"Failed to analyze code: {e}")
    
    def _build_analysis_prompt(
        self,
        file_data: Dict[str, Any],
        pr_context: Dict[str, Any],
        config: Dict[str, Any]
    ) -> str:
        """Build analysis prompt for AI model"""
        
        filename = file_data["filename"]
        patch = file_data["patch"]
        focus_areas = config.get("focus_areas", settings.DEFAULT_FOCUS_AREAS)
        review_level = config.get("review_level", settings.DEFAULT_REVIEW_LEVEL)
        
        # Get file extension for context
        file_ext = filename.split('.')[-1] if '.' in filename else ""
        
        # Build focus areas text
        focus_text = self._build_focus_areas_text(focus_areas)
        
        # Build review level instructions
        level_instructions = self._build_review_level_instructions(review_level)
        
        prompt = f"""
You are an expert code reviewer adhering to clean code and SOLID principles analyzing a pull request . Please analyze the following code changes and provide specific, actionable feedback.

**File:** {filename}
**File Type:** {file_ext}
**PR Context:** {pr_context.get('title', 'N/A')}
**Changes:** +{file_data.get('additions', 0)} -{file_data.get('deletions', 0)}

**Code Diff:**
```diff
{patch}
```

**Review Instructions:**
{level_instructions}

**Focus Areas:**
{focus_text}

**Requirements:**
- Only comment on lines that are changed (marked with + or -)
- Provide specific line numbers from the diff
- Give actionable suggestions with code examples when possible
- Be constructive and educational in tone
- Avoid nitpicking unless in strict mode
- Focus on issues that could impact functionality, security, or maintainability

**Response Format:**
Return a JSON array of comments. Each comment should have:
- "line": line number from the diff (required)
- "type": "error" | "warning" | "suggestion" (required)
- "category": one of {focus_areas} (required)
- "message": clear description of the issue (required)
- "suggestion": specific improvement recommendation (optional)
- "code_example": example code snippet if helpful (optional)

**Example:**
```json
[
  {{
    "line": 10,
    "type": "warning",
    "category": "security",
    "message": "Potential SQL injection vulnerability detected",
    "suggestion": "Use parameterized queries to prevent SQL injection",
    "code_example": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"
  }}
]
```

Only return the JSON array, no other text.
"""
        
        return prompt
    
    def _build_focus_areas_text(self, focus_areas: List[str]) -> str:
        """Build focus areas description"""
        descriptions = {
            "security": "Look for security vulnerabilities, authentication issues, input validation problems, and potential exploits",
            "performance": "Identify performance bottlenecks, inefficient algorithms, memory leaks, and scalability issues",
            "maintainability": "Check code organization, readability, complexity, and long-term maintainability",
            "style": "Review code formatting, naming conventions, and adherence to best practices",
            "testing": "Evaluate test coverage, test quality, and missing test cases"
        }
        
        areas_text = []
        for area in focus_areas:
            if area in descriptions:
                areas_text.append(f"- **{area.title()}**: {descriptions[area]}")
        
        return "\n".join(areas_text)
    
    def _build_review_level_instructions(self, review_level: str) -> str:
        """Build review level specific instructions"""
        instructions = {
            "minimal": "Only flag critical security issues, bugs, and major architectural problems. Skip minor style issues.",
            "standard": "Provide balanced feedback on security, performance, and maintainability. Include important style issues.",
            "strict": "Comprehensive review including all issues, style problems, and potential improvements. Be thorough."
        }
        
        return instructions.get(review_level, instructions["minimal"])
    
    def _parse_ai_response(self, response: str, filename: str) -> List[Dict[str, Any]]:
        """Parse AI response into structured comments"""
        try:
            import json
            
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            response = response.strip()
            
            comments_data = json.loads(response)
            
            if not isinstance(comments_data, list):
                self.logger.warning(f"AI response is not a list: {type(comments_data)}")
                return []
            
            comments = []
            for comment_data in comments_data:
                if not isinstance(comment_data, dict):
                    continue
                
                # Validate required fields
                if not all(key in comment_data for key in ["line", "type", "category", "message"]):
                    self.logger.warning(f"Invalid comment data: {comment_data}")
                    continue
                
                comment = {
                    "filename": filename,
                    "line": comment_data["line"],
                    "type": comment_data["type"],
                    "category": comment_data["category"],
                    "message": comment_data["message"],
                    "suggestion": comment_data.get("suggestion"),
                    "code_example": comment_data.get("code_example")
                }
                comments.append(comment)
            
            return comments
            
        except json.JSONDecodeError as e:
            self.log_error("JSON parsing", e, filename=filename, response=response[:200])
            return []
        except Exception as e:
            self.log_error("AI response parsing", e, filename=filename)
            return []
    
    async def generate_review_summary(
        self,
        all_comments: List[Dict[str, Any]],
        pr_context: Dict[str, Any]
    ) -> str:
        """Generate a summary for the entire PR review"""
        try:
            if not all_comments:
                return "✅ No issues found in this PR!"
            
            # Count issues by type and category
            issue_counts = {}
            category_counts = {}
            
            for comment in all_comments:
                issue_type = comment.get("type", "suggestion")
                category = comment.get("category", "general")
                
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
                category_counts[category] = category_counts.get(category, 0) + 1
            
            # Build summary
            total_issues = len(all_comments)
            summary = f"🤖 **BoxedBot Review Summary**\n\n"
            summary += f"Found {total_issues} potential improvement{'s' if total_issues != 1 else ''}:\n\n"
            
            # Add issue type breakdown
            type_emojis = {"error": "🚨", "warning": "⚠️", "suggestion": "💡"}
            for issue_type, count in sorted(issue_counts.items()):
                emoji = type_emojis.get(issue_type, "📝")
                summary += f"- {emoji} {count} {issue_type}{'s' if count != 1 else ''}\n"
            
            summary += "\n**Areas of Focus:**\n"
            for category, count in sorted(category_counts.items()):
                summary += f"- {category.title()}: {count} issue{'s' if count != 1 else ''}\n"
            
            summary += "\n---\n"
            summary += "Please review the specific comments below. "
            summary += "Reply to individual comments if you need clarification or disagree with a suggestion."
            
            return summary
            
        except Exception as e:
            self.log_error("Review summary generation", e)
            return "🤖 **BoxedBot Review Summary**\n\nReview completed. Please see individual comments below."