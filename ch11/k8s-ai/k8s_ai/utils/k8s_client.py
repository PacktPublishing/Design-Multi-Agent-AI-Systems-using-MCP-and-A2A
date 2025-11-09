"""Kubernetes client utilities for dynamic cluster access."""

import base64
import tempfile
from typing import Any

from kubernetes import client, config
from kubernetes.client.api_client import ApiClient
from kubernetes.client.configuration import Configuration


class KubernetesCredentials:
    """Kubernetes cluster credentials."""

    def __init__(
        self,
        api_server: str,
        token: str = "",
        ca_certificate: str = "",
        namespace: str = "default",
        client_cert: str = "",
        client_key: str = "",
    ):
        self.api_server = api_server
        self.token = token
        self.ca_certificate = ca_certificate
        self.namespace = namespace
        self.client_cert = client_cert
        self.client_key = client_key

    @classmethod
    def from_dict(cls, credentials: dict[str, Any]) -> "KubernetesCredentials":
        """Create credentials from dictionary."""
        return cls(
            api_server=credentials["api_server"],
            token=credentials.get("token", ""),
            ca_certificate=credentials.get("ca_certificate", ""),
            namespace=credentials.get("namespace", "default"),
            client_cert=credentials.get("client_cert", ""),
            client_key=credentials.get("client_key", ""),
        )


class DynamicKubernetesClient:
    """Creates Kubernetes clients dynamically from provided credentials."""

    def __init__(self, credentials: KubernetesCredentials):
        self.credentials = credentials
        self._client = None
        self._api_client = None

    def _create_configuration(self) -> Configuration:
        """Create Kubernetes configuration from credentials."""
        configuration = Configuration()
        configuration.host = self.credentials.api_server

        # Handle authentication
        if self.credentials.token:
            # Token-based authentication
            configuration.api_key = {"authorization": f"Bearer {self.credentials.token}"}
        elif self.credentials.client_cert and self.credentials.client_key:
            # Client certificate authentication
            with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                f.write(self.credentials.client_cert)
                configuration.cert_file = f.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                f.write(self.credentials.client_key)
                configuration.key_file = f.name

        # Handle CA certificate
        if self.credentials.ca_certificate:
            # Write CA cert to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.crt', delete=False) as f:
                f.write(self.credentials.ca_certificate)
                configuration.ssl_ca_cert = f.name
        else:
            # Skip TLS verification if no CA provided (not recommended for production)
            configuration.verify_ssl = False

        return configuration

    def get_api_client(self) -> ApiClient:
        """Get Kubernetes API client."""
        if self._api_client is None:
            configuration = self._create_configuration()
            self._api_client = ApiClient(configuration)
        return self._api_client

    def get_core_v1_api(self) -> client.CoreV1Api:
        """Get Core V1 API client."""
        return client.CoreV1Api(self.get_api_client())

    def get_apps_v1_api(self) -> client.AppsV1Api:
        """Get Apps V1 API client."""
        return client.AppsV1Api(self.get_api_client())

    def get_networking_v1_api(self) -> client.NetworkingV1Api:
        """Get Networking V1 API client."""
        return client.NetworkingV1Api(self.get_api_client())

    def list_pods(self, namespace: str | None = None) -> client.V1PodList:
        """List pods in namespace or across all namespaces if namespace='all'."""
        namespace = namespace or self.credentials.namespace
        core_v1 = self.get_core_v1_api()

        # Handle "all" as a special case to list across all namespaces
        if namespace and namespace.lower() == "all":
            return core_v1.list_pod_for_all_namespaces()

        return core_v1.list_namespaced_pod(namespace)

    def get_pod_logs(
        self,
        pod_name: str,
        namespace: str | None = None,
        container: str | None = None,
        tail_lines: int | None = None
    ) -> str:
        """Get pod logs."""
        namespace = namespace or self.credentials.namespace
        core_v1 = self.get_core_v1_api()

        kwargs = {}
        if container:
            kwargs["container"] = container
        if tail_lines:
            kwargs["tail_lines"] = tail_lines

        return core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            **kwargs
        )

    def get_events(self, namespace: str | None = None) -> client.CoreV1EventList:
        """Get events in namespace."""
        namespace = namespace or self.credentials.namespace
        core_v1 = self.get_core_v1_api()
        return core_v1.list_namespaced_event(namespace)

    def get_pod(self, pod_name: str, namespace: str | None = None) -> client.V1Pod:
        """Get specific pod."""
        namespace = namespace or self.credentials.namespace
        core_v1 = self.get_core_v1_api()
        return core_v1.read_namespaced_pod(pod_name, namespace)

    def get_deployment(self, deployment_name: str, namespace: str | None = None) -> client.V1Deployment:
        """Get specific deployment."""
        namespace = namespace or self.credentials.namespace
        apps_v1 = self.get_apps_v1_api()
        return apps_v1.read_namespaced_deployment(deployment_name, namespace)

    def close(self):
        """Clean up resources."""
        if self._api_client:
            self._api_client.close()


def create_k8s_client(credentials_dict: dict[str, Any]) -> DynamicKubernetesClient:
    """Create Kubernetes client from credentials dictionary."""
    credentials = KubernetesCredentials.from_dict(credentials_dict)
    return DynamicKubernetesClient(credentials)