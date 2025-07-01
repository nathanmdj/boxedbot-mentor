"""
Webhook endpoints for GitHub integration
"""

from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.exceptions import WebhookException, AuthenticationException
from app.services.webhook_service import WebhookService

router = APIRouter()
logger = get_logger(__name__)


@router.post("/github")
async def github_webhook(request: Request) -> Dict[str, Any]:
    """
    Handle GitHub webhook events
    
    This endpoint receives webhook events from GitHub and processes them
    according to the event type. Supported events include:
    - pull_request (opened, synchronize, reopened)
    - pull_request_review
    - installation
    - ping
    """
    try:
        webhook_service = WebhookService()
        result = await webhook_service.process_webhook(request)
        
        return result
        
    except AuthenticationException as e:
        logger.error(f"Webhook authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": str(e)
                }
            }
        )
    
    except WebhookException as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.code,
                    "message": str(e),
                    "event_type": getattr(e, 'event_type', None)
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Unexpected webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred"
                }
            }
        )


@router.get("/github/events")
async def get_supported_events() -> Dict[str, Any]:
    """
    Get list of supported webhook events
    
    Returns information about which GitHub webhook events
    BoxedBot can process.
    """
    webhook_service = WebhookService()
    
    return {
        "supported_events": webhook_service.get_supported_events(),
        "description": "List of GitHub webhook events supported by BoxedBot",
        "webhook_url": "/api/v1/webhooks/github"
    }


@router.post("/test")
async def test_webhook(request: Request) -> Dict[str, Any]:
    """
    Test endpoint for webhook debugging
    
    This endpoint can be used during development to test
    webhook payload processing without GitHub's signature verification.
    Only available in debug mode.
    """
    from app.core.config import settings
    
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test endpoint not available in production"
        )
    
    try:
        # Get the request body
        payload = await request.body()
        headers = dict(request.headers)
        
        logger.info("Test webhook received", extra={
            "headers": headers,
            "payload_size": len(payload)
        })
        
        return {
            "status": "received",
            "message": "Test webhook processed successfully",
            "headers": headers,
            "payload_size": len(payload)
        }
        
    except Exception as e:
        logger.error(f"Test webhook error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e)}
        )