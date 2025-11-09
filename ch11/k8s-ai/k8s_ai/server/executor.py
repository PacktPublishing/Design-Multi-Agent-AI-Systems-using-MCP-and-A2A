"""A2A agent executor for k8s-ai."""

from typing_extensions import override

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message

from ..core.kubectl import KubectlExecutor


class K8sAgentExecutor(AgentExecutor):
    """Kubernetes AI Agent executor for A2A server."""
    
    def __init__(self, context: str):
        """Initialize with Kubernetes context."""
        self.kubectl_executor = KubectlExecutor(context=context)
        self.context = context
    
    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute the agent request."""
        # Get the user input from the request context
        user_message = context.get_user_input()
        
        if not user_message:
            await event_queue.enqueue_event(new_agent_text_message("No message provided"))
            return
        
        # Create conversation context
        messages = [
            {'role': 'system', 'content': f'You are a Kubernetes expert ready to help. You have access to kubectl commands for the context: {self.context}'},
            {'role': 'user', 'content': user_message}
        ]
        
        # Process with OpenAI and kubectl
        try:
            response = self.kubectl_executor.send_message(messages)
            await event_queue.enqueue_event(new_agent_text_message(response))
        except Exception as e:
            await event_queue.enqueue_event(new_agent_text_message(f"Error: {str(e)}"))
    
    @override
    async def cancel(
        self,
        context: RequestContext,
        event_queue: EventQueue
    ) -> None:
        """Cancel the agent execution."""
        await event_queue.enqueue_event(new_agent_text_message("Request cancelled"))
