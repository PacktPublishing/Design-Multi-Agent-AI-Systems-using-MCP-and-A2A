"""Cluster session management for multi-cluster support."""

import secrets
import tempfile
import yaml
from datetime import datetime, timedelta
from typing import Any, Optional

from .k8s_client import DynamicKubernetesClient, KubernetesCredentials


class ClusterSession:
    """Represents a cluster session with temporary credentials."""

    def __init__(
        self,
        session_token: str,
        cluster_name: str,
        credentials: KubernetesCredentials,
        expires_at: datetime,
        client_api_key: Optional[str] = None,
    ):
        self.session_token = session_token
        self.cluster_name = cluster_name
        self.credentials = credentials
        self.expires_at = expires_at
        self.client_api_key = client_api_key  # Track which API key created this session
        self.created_at = datetime.utcnow()
        self._k8s_client: Optional[DynamicKubernetesClient] = None

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expires_at

    def get_k8s_client(self) -> DynamicKubernetesClient:
        """Get Kubernetes client for this session."""
        if self._k8s_client is None:
            self._k8s_client = DynamicKubernetesClient(self.credentials)
        return self._k8s_client

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._k8s_client:
            self._k8s_client.close()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "session_token": self.session_token,
            "cluster_name": self.cluster_name,
            "api_server": self.credentials.api_server,
            "namespace": self.credentials.namespace,
            "created_at": self.created_at.isoformat() + "Z",
            "expires_at": self.expires_at.isoformat() + "Z",
            "is_expired": self.is_expired(),
        }


class ClusterSessionManager:
    """Manages cluster sessions with automatic cleanup."""

    def __init__(self):
        self._sessions: dict[str, ClusterSession] = {}

    def create_session(
        self,
        cluster_name: str,
        kubeconfig_yaml: str,
        context: Optional[str] = None,
        ttl_hours: float = 24.0,
        client_api_key: Optional[str] = None,
    ) -> str:
        """Create a new session with cluster credentials and return session token."""
        # Validate TTL
        if ttl_hours > 168:  # Max 7 days
            raise ValueError("TTL cannot exceed 168 hours (7 days)")

        # Parse kubeconfig
        try:
            kubeconfig = yaml.safe_load(kubeconfig_yaml)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid kubeconfig YAML: {e}")

        # Extract credentials from kubeconfig
        credentials = self._extract_credentials_from_kubeconfig(
            kubeconfig, context
        )

        # Generate session token
        session_token = self._generate_session_token()

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        # Create session
        session = ClusterSession(
            session_token=session_token,
            cluster_name=cluster_name,
            credentials=credentials,
            expires_at=expires_at,
            client_api_key=client_api_key,
        )

        # Store session
        self._sessions[session_token] = session

        # Clean up expired sessions
        self._cleanup_expired_sessions()

        return session_token

    def get_session(self, session_token: str) -> Optional[ClusterSession]:
        """Get session by token."""
        session = self._sessions.get(session_token)
        if session and session.is_expired():
            self.delete_session(session_token)
            return None
        return session

    def delete_session(self, session_token: str) -> bool:
        """Delete a cluster session."""
        session = self._sessions.pop(session_token, None)
        if session:
            session.cleanup()
            return True
        return False

    def list_sessions(self, client_api_key: Optional[str] = None) -> list[dict[str, Any]]:
        """List active sessions. If client_api_key provided, only return that client's sessions."""
        self._cleanup_expired_sessions()
        sessions = self._sessions.values()

        # Filter by client API key if provided
        if client_api_key:
            sessions = [s for s in sessions if s.client_api_key == client_api_key]

        return [session.to_dict() for session in sessions]

    def _extract_credentials_from_kubeconfig(
        self, kubeconfig: dict[str, Any], context_name: Optional[str] = None
    ) -> KubernetesCredentials:
        """Extract credentials from kubeconfig."""
        # Determine context to use
        if context_name:
            context = next(
                (ctx for ctx in kubeconfig.get("contexts", []) if ctx["name"] == context_name),
                None,
            )
            if not context:
                raise ValueError(f"Context '{context_name}' not found in kubeconfig")
        else:
            current_context = kubeconfig.get("current-context")
            if not current_context:
                raise ValueError("No current-context in kubeconfig and no context specified")
            context = next(
                (ctx for ctx in kubeconfig.get("contexts", []) if ctx["name"] == current_context),
                None,
            )
            if not context:
                raise ValueError(f"Current context '{current_context}' not found")

        # Get cluster and user info
        cluster_name = context["context"]["cluster"]
        user_name = context["context"]["user"]
        namespace = context["context"].get("namespace", "default")

        # Find cluster info
        cluster = next(
            (c for c in kubeconfig.get("clusters", []) if c["name"] == cluster_name),
            None,
        )
        if not cluster:
            raise ValueError(f"Cluster '{cluster_name}' not found in kubeconfig")

        # Find user info
        user = next(
            (u for u in kubeconfig.get("users", []) if u["name"] == user_name),
            None,
        )
        if not user:
            raise ValueError(f"User '{user_name}' not found in kubeconfig")

        # Extract cluster info
        cluster_info = cluster["cluster"]
        api_server = cluster_info["server"]

        # Handle CA certificate
        ca_certificate = ""
        if "certificate-authority-data" in cluster_info:
            import base64
            ca_certificate = base64.b64decode(
                cluster_info["certificate-authority-data"]
            ).decode("utf-8")
        elif "certificate-authority" in cluster_info:
            with open(cluster_info["certificate-authority"]) as f:
                ca_certificate = f.read()

        # Extract user credentials
        user_info = user["user"]
        token = ""
        client_cert = ""
        client_key = ""

        if "token" in user_info:
            token = user_info["token"]
        elif "client-certificate-data" in user_info and "client-key-data" in user_info:
            import base64
            client_cert = base64.b64decode(
                user_info["client-certificate-data"]
            ).decode("utf-8")
            client_key = base64.b64decode(
                user_info["client-key-data"]
            ).decode("utf-8")
        elif "client-certificate" in user_info and "client-key" in user_info:
            with open(user_info["client-certificate"]) as f:
                client_cert = f.read()
            with open(user_info["client-key"]) as f:
                client_key = f.read()
        else:
            raise ValueError("No supported authentication method found in kubeconfig")

        return KubernetesCredentials(
            api_server=api_server,
            token=token,
            ca_certificate=ca_certificate,
            namespace=namespace,
            client_cert=client_cert,
            client_key=client_key,
        )

    def _generate_session_token(self) -> str:
        """Generate a secure session token."""
        return f"k8s-ai-session-{secrets.token_urlsafe(32)}"

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired sessions."""
        expired_tokens = [
            token for token, session in self._sessions.items()
            if session.is_expired()
        ]
        for token in expired_tokens:
            self.unregister_cluster(token)


# Global session manager instance
session_manager = ClusterSessionManager()