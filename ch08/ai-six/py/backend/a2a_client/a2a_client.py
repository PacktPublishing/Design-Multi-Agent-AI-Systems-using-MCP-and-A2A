"""A2A (Agent-to-Agent) client for communicating with remote A2A agents."""

import httpx
import requests
from typing import Optional, AsyncGenerator
from dataclasses import dataclass
import logging

from a2a.client import ClientFactory, ClientConfig
from a2a.client.helpers import create_text_message_object
from a2a.client.auth.credentials import CredentialService
from a2a.client.auth.interceptor import AuthInterceptor
from a2a.client.middleware import ClientCallContext
from a2a.types import AgentCard, Role


@dataclass
class A2AServerConfig:
    """Configuration for an A2A server."""
    name: str
    url: str
    agent_card_url: Optional[str] = None
    timeout: float = 30.0
    api_key: Optional[str] = None

    def __post_init__(self):
        """Set default agent card URL if not provided."""
        if self.agent_card_url is None:
            self.agent_card_url = f"{self.url.rstrip('/')}/.well-known/agent-card.json"


class SimpleCredentialService(CredentialService):
    """Simple credential service that stores a single credential per scheme."""
    
    def __init__(self):
        self._credentials: dict[str, str] = {}
    
    def add_credential(self, scheme_name: str, credential: str):
        """Add a credential for a security scheme."""
        self._credentials[scheme_name] = credential
    
    async def get_credentials(
        self,
        security_scheme_name: str,
        context: ClientCallContext | None,
    ) -> str | None:
        """Get credential for the given scheme."""
        return self._credentials.get(security_scheme_name)


class A2AClient:
    """Client for communicating with A2A agents."""
    def __init__(self):
        self._agent_cards: dict[str, AgentCard] = {}
        self._clients: dict[str, object] = {}
        self._server_configs: dict[str, A2AServerConfig] = {}
        self.logger = logging.getLogger(__name__)

    async def get_skills(self, server_name: str) -> list:
        """Get agent skills, discovering agent if needed.

        Args:
            server_name: Name of the A2A server

        Returns:
            List of AgentSkill objects from the agent card
        """
        # Discover agent if not already cached
        if server_name not in self._agent_cards:
            if server_name not in self._server_configs:
                raise ValueError(f"No configuration found for server {server_name}")
            server_config = self._server_configs[server_name]
            await self._discover_agent(server_config)

        return self._agent_cards[server_name].skills or []

    async def _discover_agent(self, server_config: A2AServerConfig) -> AgentCard:
        """Discover an A2A agent by fetching its agent card.

        Args:
            server_config: Configuration for the A2A server

        Returns:
            AgentCard object containing agent metadata

        Raises:
            Exception: If agent card cannot be fetched
        """
        try:
            # Store server config for later use
            self._server_configs[server_config.name] = server_config
            
            # Fetch agent card
            response = requests.get(
                server_config.agent_card_url,
                timeout=server_config.timeout
            )
            response.raise_for_status()
            card_data = response.json()

            # Create and cache agent card
            agent_card = AgentCard(**card_data)
            self._agent_cards[server_config.name] = agent_card

            return agent_card

        except Exception as e:
            raise Exception(f"Failed to discover agent {server_config.name}: {e}")


    async def send_message(self, server_name: str, message: str) -> AsyncGenerator[str, None]:
        """Send a message to an A2A agent and stream responses.
        
        Args:
            server_name: Name of the A2A server
            message: Message text to send
            
        Yields:
            Response text chunks from the agent
        """
        if server_name not in self._agent_cards:
            raise ValueError(f"Agent {server_name} not discovered yet")

        agent_card = self._agent_cards[server_name]

        # Create client if not exists - use a persistent HTTP client
        if server_name not in self._clients:
            # Get server config for authentication
            server_config = self._server_configs.get(server_name)
            
            # Create HTTP client and credential service
            http_client = httpx.AsyncClient(timeout=30)
            
            # Set up authentication if API key is provided
            interceptors = []
            if server_config and server_config.api_key:
                credential_service = SimpleCredentialService()
                # Add credential for BearerAuth scheme (matching server security scheme)
                credential_service.add_credential('BearerAuth', server_config.api_key)
                auth_interceptor = AuthInterceptor(credential_service)
                interceptors.append(auth_interceptor)
            
            config = ClientConfig(httpx_client=http_client)
            factory = ClientFactory(config)
            client = factory.create(agent_card, interceptors=interceptors)
            
            self._clients[server_name] = {
                'client': client,
                'http_client': http_client
            }

        client = self._clients[server_name]['client']

        # Create message object
        message_obj = create_text_message_object(Role.user, message)

        # Send message and yield responses
        async for event in client.send_message(message_obj):
            if hasattr(event, 'parts') and event.parts:
                for part in event.parts:
                    # Check for TextPart in root attribute
                    if hasattr(part, 'root'):
                        root = part.root
                        if hasattr(root, 'text'):
                            text = root.text
                            # Yield the text in smaller chunks to simulate streaming
                            # Split by sentences or newlines for more granular updates
                            lines = text.split('\n')
                            for line in lines:
                                if line.strip():
                                    yield line + '\n'
                    # Direct text attribute
                    elif hasattr(part, 'text'):
                        text = part.text
                        lines = text.split('\n')
                        for line in lines:
                            if line.strip():
                                yield line + '\n'

    async def execute_skill(self, server_name: str, skill_name: str, parameters: dict) -> str:
        """Execute a specific skill on an A2A agent.

        Args:
            server_name: Name of the A2A server
            skill_name: Name of the skill to execute
            parameters: Parameters for the skill

        Returns:
            Combined response text from the skill
        """
        # Format skill message with parameters
        if parameters:
            # If we have specific parameters, use them to construct the message
            message = parameters.get('message', parameters.get('query', parameters.get('input', 'show me all pods')))
        else:
            # Default message for the skill
            message = "show me all pods"

        # Send message and collect all response text
        response_parts = []
        async for response_chunk in self.send_message(server_name, message):
            response_parts.append(response_chunk)

        return ''.join(response_parts)

    async def cleanup(self):
        """Cleanup A2A client resources."""
        # Close all HTTP clients
        for server_name, client_info in self._clients.items():
            await client_info['http_client'].aclose()

        # Clear cached clients and agent cards
        self._clients.clear()
        self._agent_cards.clear()
