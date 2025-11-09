"""Out-of-band admin API for cluster management."""

import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from ..utils.cluster_sessions import session_manager

logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

class SessionCreateRequest(BaseModel):
    cluster_name: str
    kubeconfig: str
    context: str | None = None
    ttl_hours: float = 24.0

class SessionCreateResponse(BaseModel):
    success: bool
    session_token: str | None = None
    cluster_name: str | None = None
    api_server: str | None = None
    namespace: str | None = None
    connectivity_status: str | None = None
    connectivity_message: str | None = None
    expires_at: str | None = None
    error: str | None = None

class SessionListResponse(BaseModel):
    total_sessions: int
    sessions: list[Dict[str, Any]]

def create_admin_app(api_key_manager=None) -> FastAPI:
    """Create FastAPI app for admin operations."""
    app = FastAPI(
        title="k8s-ai A2A Admin API",
        description="Out-of-band cluster management for k8s-ai A2A server",
        version="1.0.0"
    )

    def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
        """Verify admin API token using keys from ApiKeyManager."""
        if api_key_manager:
            # Use keys from ApiKeyManager (keys.json)
            if api_key_manager.validate_key(credentials.credentials):
                return credentials.credentials

        # Fall back to environment variable if no ApiKeyManager provided
        import os
        admin_key = os.getenv("A2A_API_KEY")
        if admin_key and credentials.credentials == admin_key:
            return credentials.credentials

        raise HTTPException(status_code=401, detail="Invalid admin API key")

    @app.post("/sessions", response_model=SessionCreateResponse)
    async def create_session(
        request: SessionCreateRequest,
        api_key: str = Depends(verify_admin_token)
    ):
        """Create a new cluster session with temporary credentials."""
        try:
            # Create the session
            session_token = session_manager.create_session(
                cluster_name=request.cluster_name,
                kubeconfig_yaml=request.kubeconfig,
                context=request.context,
                ttl_hours=request.ttl_hours,
                client_api_key=api_key  # Track which API key created this session
            )

            # Test connectivity
            session = session_manager.get_session(session_token)
            if session:
                try:
                    k8s_client = session.get_k8s_client()
                    # Simple connectivity test
                    version_info = k8s_client.get_api_client().api_version
                    connectivity_status = "connected"
                    connectivity_message = f"Successfully connected to Kubernetes API"
                except Exception as e:
                    connectivity_status = "warning"
                    connectivity_message = f"Registered but connectivity test failed: {str(e)}"
            else:
                connectivity_status = "error"
                connectivity_message = "Session creation failed"

            return SessionCreateResponse(
                success=True,
                session_token=session_token,
                cluster_name=request.cluster_name,
                api_server=session.credentials.api_server if session else "unknown",
                namespace=session.credentials.namespace if session else "default",
                connectivity_status=connectivity_status,
                connectivity_message=connectivity_message,
                expires_at=session.expires_at.isoformat() + "Z" if session else None
            )

        except ValueError as e:
            logger.error(f"Validation error in create_session: {e}")
            return SessionCreateResponse(
                success=False,
                error=f"Configuration error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error in create_session: {e}")
            return SessionCreateResponse(
                success=False,
                error=f"Session creation failed: {str(e)}"
            )

    @app.get("/sessions", response_model=SessionListResponse)
    async def list_all_sessions(_: str = Depends(verify_admin_token)):
        """List all active sessions (admin only)."""
        try:
            sessions = session_manager.list_sessions()
            return SessionListResponse(
                total_sessions=len(sessions),
                sessions=sessions
            )
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

    @app.get("/sessions/mine", response_model=SessionListResponse)
    async def list_my_sessions(api_key: str = Depends(verify_admin_token)):
        """List sessions created by the authenticated client."""
        try:
            sessions = session_manager.list_sessions(client_api_key=api_key)
            return SessionListResponse(
                total_sessions=len(sessions),
                sessions=sessions
            )
        except Exception as e:
            logger.error(f"Error listing client sessions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

    @app.delete("/sessions/{session_token}")
    async def delete_session(
        session_token: str,
        api_key: str = Depends(verify_admin_token)
    ):
        """Delete a cluster session."""
        try:
            # Get session info before removing
            session = session_manager.get_session(session_token)
            if session:
                # Verify the client owns this session (unless they're admin with all access)
                # For now, allow any authenticated client to delete any session
                # TODO: Add proper authorization checks
                cluster_name = session.cluster_name
                deleted = session_manager.delete_session(session_token)
            else:
                cluster_name = "unknown"
                deleted = False

            return {
                "success": True,
                "session_token": session_token,
                "cluster_name": cluster_name,
                "deleted": deleted,
                "message": "Session removed successfully" if deleted else "Session not found or already expired"
            }

        except Exception as e:
            logger.error(f"Error in delete_session: {e}")
            raise HTTPException(status_code=500, detail=f"Session deletion failed: {str(e)}")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "k8s-ai-a2a-admin"}

    return app

def serve_admin_api(host: str = "0.0.0.0", port: int = 9998):
    """Start the admin API server."""
    app = create_admin_app()
    logger.info(f"Starting k8s-ai A2A Admin API on {host}:{port}")
    logger.info("Admin API endpoints:")
    logger.info(f"  POST   http://{host}:{port}/sessions")
    logger.info(f"  GET    http://{host}:{port}/sessions")
    logger.info(f"  GET    http://{host}:{port}/sessions/mine")
    logger.info(f"  DELETE http://{host}:{port}/sessions/{{session_token}}")
    logger.info(f"  GET    http://{host}:{port}/health")

    uvicorn.run(app, host=host, port=port, log_config=None)