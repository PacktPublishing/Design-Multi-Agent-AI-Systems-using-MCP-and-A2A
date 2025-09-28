from typing import Optional
from dataclasses import dataclass
from abc import ABC


@dataclass
class ToolCall:
    """A class to represent a tool call made by the LLM."""
    id: str
    name: str
    arguments: str
    required: list[str]


@dataclass
class Usage:
    """A class to represent the usage information."""
    input_tokens: int
    output_tokens: int

@dataclass
class Message(ABC):
    """Base class for all message types - provider agnostic."""
    content: str
    role: str = ""


@dataclass
class UserMessage(Message):
    """User message containing input from the user."""
    role: str = "user"


@dataclass  
class SystemMessage(Message):
    """System message containing instructions or context."""
    role: str = "system"


@dataclass
class AssistantMessage(Message):
    """Assistant message containing model response."""
    role: str = "assistant"
    tool_calls: Optional[list[ToolCall]] = None
    usage: Optional[Usage] = None


@dataclass
class ToolMessage(Message):
    """Tool message containing tool execution result."""
    name: str = ""
    tool_call_id: str = ""
    role: str = "tool"
