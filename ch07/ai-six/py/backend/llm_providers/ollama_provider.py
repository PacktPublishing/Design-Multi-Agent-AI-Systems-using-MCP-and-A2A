import json
from dataclasses import asdict

from backend.object_model import LLMProvider, ToolCall, Usage, Tool, AssistantMessage, Message
import ollama

class OllamaProvider(LLMProvider):
    def __init__(self, model: str):
        self.model = model

    @staticmethod
    def _tool2dict(tool: Tool) -> dict:
        """Convert the tool to a dictionary format for Ollama."""
        return {
            'type': 'function',
            'function': {
                'name': tool.name,
                'description': tool.description,
                'parameters': {
                    'type': 'object',
                    'required': list(tool.required),
                    'properties': {
                        param.name: {
                            'type': param.type,
                            'description': param.description
                        } for param in tool.parameters
                    },
                }
            }
        }

    @staticmethod
    def _fix_tool_call_arguments(messages):
        for message in messages:
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                continue
            for call in tool_calls:
                func = call.get("function")
                if func and isinstance(func.get("arguments"), str):
                    try:
                        func["arguments"] = json.loads(func["arguments"])
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON in function.arguments: {func['arguments']}") from e


    def send(self, messages: list[Message], tool_dict: dict[str, Tool], model: str | None = None) -> AssistantMessage:
        """Send a message to the local Ollama model and receive a response."""
        if model is None:
            model = self.model

        tool_data = [tool.run for tool in tool_dict.values()] + [self._tool2dict(tool) for tool in tool_dict.values()]

        # Convert Message objects to dictionaries for Ollama API
        message_dicts = [asdict(msg) for msg in messages]
        
        OllamaProvider._fix_tool_call_arguments(message_dicts)
        response: ollama.ChatResponse = ollama.chat(
            model,
            messages=message_dicts,
            tools=tool_data
        )

        tool_calls = response.message.tool_calls or []

        # Extract and map usage data
        input_tokens = response.get('prompt_eval_count', 0)
        output_tokens = response.get('eval_count', 0)

        return AssistantMessage(
            content=response.message.content,
            role=response.message.role,
            tool_calls=[
                ToolCall(
                    id=tool_call.function.name,
                    name=tool_call.function.name,
                    arguments=json.dumps(tool_call.function.arguments),
                    required=list(tool_dict[tool_call.function.name].required)
                ) for tool_call in tool_calls if tool_call
            ] if tool_calls else None,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        )
    @property

    def models(self) -> list[str]:
        """Get the list of available models."""
        return [self.model]
