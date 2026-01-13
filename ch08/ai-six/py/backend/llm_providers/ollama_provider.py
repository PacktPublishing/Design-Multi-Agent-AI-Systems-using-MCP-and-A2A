import json
from dataclasses import asdict
from typing import Iterator

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
    def _tool_call2dict(tool_call: ToolCall) -> dict:
        """Convert a ToolCall to Ollama API format."""
        return {
            "id": tool_call.id,
            "type": "function",
            "function": {
                "name": tool_call.name,
                "arguments": json.loads(tool_call.arguments) if isinstance(tool_call.arguments, str) else tool_call.arguments
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

        tool_data = [self._tool2dict(tool) for tool in tool_dict.values()]

        # Convert Message objects to dictionaries for Ollama API
        message_dicts = []
        for msg in messages:
            msg_dict = asdict(msg)
            # Convert tool_calls to Ollama format if present
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                msg_dict['tool_calls'] = [self._tool_call2dict(tc) for tc in msg.tool_calls]
            message_dicts.append(msg_dict)
        
        OllamaProvider._fix_tool_call_arguments(message_dicts)
        try:
            response: ollama.ChatResponse = ollama.chat(
                model,
                messages=message_dicts,
                tools=tool_data
            )
        except Exception as e:
            raise

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
                    arguments=json.dumps(tool_call.function.arguments or {}),
                    required=list(tool_dict[tool_call.function.name].required)
                ) for tool_call in tool_calls if tool_call and tool_call.function
            ] if tool_calls else None,
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        )
    @property

    def models(self) -> list[str]:
        """Get the list of available models."""
        return [m.model for m in ollama.list().models]
