from typing import Any, Optional
import tempfile
from unittest.mock import patch

from backend.agent.config import Config
from backend.object_model import Usage, AssistantMessage, LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self):
        self.mock_responses = []
        self.stream_mock_responses = []
        self.send_calls = []  # Track calls to send
        
    def add_mock_response(self, content, tool_calls=None, input_tokens=10, output_tokens=10):
        """Add a mock response to be returned by the send method."""
        self.mock_responses.append(AssistantMessage(
            content=content,
            role="assistant",
            tool_calls=tool_calls,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens)
        ))
        
    def add_stream_mock_response(self, content, tool_calls=None, input_tokens=10, output_tokens=10):
        """Add a mock response to be returned by the stream method."""
        self.stream_mock_responses.append(AssistantMessage(
            content=content,
            role="assistant",
            tool_calls=tool_calls,
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens)
        ))
        
    def send(self, messages, tool_dict, model=None):
        """Return the next mock response and track the call."""
        # Track call for testing
        self.send_calls.append({
            'messages': messages,
            'tool_dict': tool_dict,
            'model': model
        })
        
        if not self.mock_responses:
            return AssistantMessage(
                content="Default response", 
                role="assistant", 
                tool_calls=None,
                usage=Usage(input_tokens=10, output_tokens=10)
            )
        return self.mock_responses.pop(0)
        
    def stream(self, messages, tool_dict, model=None):
        """Return a stream of mock responses."""
        if not self.stream_mock_responses:
            yield AssistantMessage(
                content="Default streaming response", 
                role="assistant", 
                tool_calls=None,
                usage=Usage(input_tokens=10, output_tokens=10)
            )
        else:
            yield self.stream_mock_responses.pop(0)
            
    @property
    def models(self):
        return ["mock-model"]
        
    def model_response_to_message(self, response):
        """Convert an assistant message to a message."""
        result = {
            "role": response.role,
            "content": response.content
        }
        
        if response.tool_calls:
            result["tool_calls"] = [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "arguments": t.arguments
                    }
                } for t in response.tool_calls
            ]
            
        return result


def create_mock_agent(
    checkpoint_interval: int = 2,
    tools_dir: Optional[str] = None,
    mcp_tools_dir: Optional[str] = None,
    memory_dir: Optional[str] = None,
    deterministic_tool_ids: bool = True
) -> dict[str, Any]:
    """
    Create a mock Engine instance and associated resources for testing.

    Args:
        checkpoint_interval: The checkpoint interval to use for the agent
        tools_dir: Directory where tools are located (defaults to a fake path)
        mcp_tools_dir: Directory where MCP tools are located (defaults to a fake path)
        memory_dir: Directory to use for session storage (defaults to a temp dir)
        deterministic_tool_ids: If True, patches the tool ID generation to use deterministic IDs

    Returns:
        A dictionary containing the agent, provider, config, and temp_dir (if created)
    """
    # Create a mock LLM provider
    llm_provider = MockLLMProvider()

    # Create a temporary directory for testing if not provided
    if memory_dir is None:
        temp_dir = tempfile.mkdtemp()
        memory_dir = temp_dir
    else:
        temp_dir = None

    # Use default directories if not provided
    if tools_dir is None:
        tools_dir = "/Users/gigi/git/ai-six/py/backend/tools"

    if mcp_tools_dir is None:
        mcp_tools_dir = "/Users/gigi/git/ai-six/py/backend/mcp_tools"

    # Create a config with the specified parameters
    from backend.agent.agent import Agent

    config = Config(
        default_model_id="mock-model",
        tools_dirs=[tools_dir] if tools_dir else [],
        mcp_tools_dirs=[mcp_tools_dir] if mcp_tools_dir else [],
        memory_dir=memory_dir,
        checkpoint_interval=checkpoint_interval
    )
    
    # Create a deterministic ID generator for testing if requested
    id_generator_patcher = None
    if deterministic_tool_ids:
        id_counter = [0]
        
        def deterministic_id_generator(original_id=None):
            id_counter[0] += 1
            return f"tool_test_id_{id_counter[0]}"
        
        id_generator_patcher = patch('backend.agent.agent.generate_tool_call_id', 
                                    side_effect=deterministic_id_generator)
        id_generator_patcher.start()
    
    # Patch provider and tool discovery to use our mock providers
    llm_provider_patcher = patch('backend.agent.agent.Agent.discover_llm_providers', return_value=[llm_provider])
    llm_provider_patcher.start()
    
    tool_manager_patcher = patch('backend.agent.tool_manager.get_tool_dict', return_value={})
    tool_manager_patcher.start()
    
    # Mock get_context_window_size to return 1000 for mock-model in tests
    model_info_patcher = patch('backend.agent.agent.get_context_window_size')
    mock_get_window_size = model_info_patcher.start()
    mock_get_window_size.return_value = 1000
    
    # Create an agent with the config
    agent = Agent(config)
    
    return {
        "agent": agent,
        "provider": llm_provider,
        "config": config,
        "temp_dir": temp_dir,  # None if memory_dir was provided
        "id_generator_patcher": id_generator_patcher,  # None if not using deterministic IDs
        "llm_provider_patcher": llm_provider_patcher,
        "tool_manager_patcher": tool_manager_patcher,
        "model_info_patcher": model_info_patcher  # None if mock-model already in model_info
    }


def cleanup_mock_agent(mock_agent_data: dict[str, Any]):
    """
    Clean up temporary resources created by create_mock_agent.
    
    Args:
        mock_agent_data: The dictionary returned by create_mock_agent
    """
    import shutil
    
    # Stop any patchers that were started
    if mock_agent_data.get("id_generator_patcher") is not None:
        mock_agent_data["id_generator_patcher"].stop()
        
    if mock_agent_data.get("llm_provider_patcher") is not None:
        mock_agent_data["llm_provider_patcher"].stop()
        
    if mock_agent_data.get("tool_discover_patcher") is not None:
        mock_agent_data["tool_discover_patcher"].stop()
        
    if mock_agent_data.get("model_info_patcher") is not None:
        mock_agent_data["model_info_patcher"].stop()
    
    # Remove the temporary directory if one was created
    if mock_agent_data.get("temp_dir") is not None:
        shutil.rmtree(mock_agent_data["temp_dir"])
