from typing import Callable, Optional
from backend.object_model import Tool, Parameter
from backend.agent.agent import Agent
from backend.agent.config import Config


class AgentTool(Tool):
    """Tool that wraps an Agent and allows sending messages to it."""
    
    def __init__(self, agent_config: Config):
        """Initialize the AgentTool with a Config."""
        self.agent = Agent(agent_config)
        self._on_tool_call_func: Optional[Callable[[str, dict, str], None]] = None
        
        # Create tool definition
        parameters = [
            Parameter(
                name='message', 
                type='string', 
                description='The message to send to the agent'
            )
        ]

        super().__init__(
            name=f"agent_{agent_config.name}",
            description=f"Send a message to the {agent_config.name} agent. {agent_config.description}",
            parameters=parameters,
            required={'message'}
        )
    
    def set_tool_call_callback(self, callback: Optional[Callable[[str, dict, str], None]]):
        """Set the callback function for tool calls made by this agent."""
        self._on_tool_call_func = callback
    
    def run(self, message: str, **kwargs) -> str:
        """
        Send a message to the agent and return the response.
        
        Args:
            message: The message to send to the agent
            **kwargs: Additional arguments (ignored)
            
        Returns:
            The agent's response
        """
        return self.agent.send_message(message, self.agent.default_model_id, on_tool_call_func=self._on_tool_call_func)
