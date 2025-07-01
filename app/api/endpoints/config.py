"""
Configuration endpoints for repository settings management
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.exceptions import ConfigurationException, GitHubAPIException
from app.services.config_service import ConfigService, RepoConfig

router = APIRouter()
logger = get_logger(__name__)


class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates"""
    enabled: Optional[bool] = Field(None, description="Enable/disable BoxedBot for repository")
    file_patterns: Optional[list] = Field(None, description="File patterns to include in review")
    exclude_patterns: Optional[list] = Field(None, description="File patterns to exclude from review")
    review_level: Optional[str] = Field(None, description="Review level: minimal, standard, strict")
    focus_areas: Optional[list] = Field(None, description="Focus areas for review")
    max_comments_per_pr: Optional[int] = Field(None, description="Maximum comments per PR")
    skip_draft_prs: Optional[bool] = Field(None, description="Skip draft pull requests")
    ai_model_override: Optional[str] = Field(None, description="Override AI model selection")


@router.get("/{repo_id}")
async def get_repository_config(
    repo_id: str,
    installation_id: Optional[int] = Query(None, description="GitHub installation ID")
) -> Dict[str, Any]:
    """
    Get configuration for a repository
    
    Returns the current configuration for the specified repository.
    If no custom configuration exists, returns the default configuration.
    
    Args:
        repo_id: Repository identifier in format "owner/repo"
        installation_id: GitHub installation ID (optional)
    """
    try:
        # Parse repo_id
        if "/" not in repo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository ID must be in format 'owner/repo'"
            )
        
        owner, repo_name = repo_id.split("/", 1)
        
        config_service = ConfigService()
        
        if installation_id:
            # Get config from repository
            config = await config_service.get_repo_config(installation_id, owner, repo_name)
        else:
            # Return default config
            config = config_service.default_config
        
        return {
            "repo_id": repo_id,
            "config": config.dict(),
            "source": "repository" if installation_id else "default"
        }
        
    except GitHubAPIException as e:
        logger.error(f"GitHub API error getting config for {repo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "GITHUB_API_ERROR",
                    "message": str(e)
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting config for {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to retrieve configuration"
                }
            }
        )


@router.post("/{repo_id}")
async def update_repository_config(
    repo_id: str,
    config_update: ConfigUpdateRequest,
    installation_id: Optional[int] = Query(None, description="GitHub installation ID")
) -> Dict[str, Any]:
    """
    Update configuration for a repository
    
    Updates the configuration for the specified repository.
    Only provided fields will be updated; others remain unchanged.
    
    Args:
        repo_id: Repository identifier in format "owner/repo"
        config_update: Configuration fields to update
        installation_id: GitHub installation ID
    """
    try:
        # Parse repo_id
        if "/" not in repo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository ID must be in format 'owner/repo'"
            )
        
        owner, repo_name = repo_id.split("/", 1)
        
        config_service = ConfigService()
        
        # Get current config
        if installation_id:
            current_config = await config_service.get_repo_config(installation_id, owner, repo_name)
        else:
            current_config = config_service.default_config
        
        # Update only provided fields
        update_data = config_update.dict(exclude_unset=True)
        updated_config_data = current_config.dict()
        updated_config_data.update(update_data)
        
        # Validate updated configuration
        try:
            updated_config = config_service.validate_config(updated_config_data)
        except ConfigurationException as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": str(e)
                    }
                }
            )
        
        # Note: In a full implementation, you would save this config
        # to a database or create a PR to update .boxedbot.yml
        logger.info(f"Configuration updated for {repo_id}", extra={
            "repo": repo_id,
            "updates": update_data
        })
        
        return {
            "status": "updated",
            "repo_id": repo_id,
            "config": updated_config.dict(),
            "changes": update_data
        }
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error updating config for {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to update configuration"
                }
            }
        )


@router.delete("/{repo_id}")
async def reset_repository_config(repo_id: str) -> Dict[str, Any]:
    """
    Reset repository configuration to defaults
    
    Removes any custom configuration and reverts to default settings.
    
    Args:
        repo_id: Repository identifier in format "owner/repo"
    """
    try:
        # Parse repo_id
        if "/" not in repo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository ID must be in format 'owner/repo'"
            )
        
        # Note: In a full implementation, this would remove
        # the configuration from storage
        logger.info(f"Configuration reset for {repo_id}")
        
        return {
            "status": "reset",
            "repo_id": repo_id,
            "message": "Configuration reset to defaults"
        }
        
    except Exception as e:
        logger.error(f"Error resetting config for {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to reset configuration"
                }
            }
        )


@router.get("/default/example")
async def get_example_config() -> Dict[str, Any]:
    """
    Get example configuration file
    
    Returns an example .boxedbot.yml configuration file
    that can be used as a starting point for repository configuration.
    """
    try:
        config_service = ConfigService()
        example_yaml = config_service.create_example_config()
        
        return {
            "filename": ".boxedbot.yml",
            "content": example_yaml,
            "description": "Example BoxedBot configuration file"
        }
        
    except Exception as e:
        logger.error(f"Error generating example config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to generate example configuration"
                }
            }
        )


@router.get("/default/schema")
async def get_config_schema() -> Dict[str, Any]:
    """
    Get configuration schema
    
    Returns the JSON schema for BoxedBot configuration,
    useful for validation and IDE support.
    """
    try:
        # Get Pydantic schema
        schema = RepoConfig.schema()
        
        return {
            "schema": schema,
            "description": "JSON schema for BoxedBot configuration"
        }
        
    except Exception as e:
        logger.error(f"Error generating config schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to generate configuration schema"
                }
            }
        )