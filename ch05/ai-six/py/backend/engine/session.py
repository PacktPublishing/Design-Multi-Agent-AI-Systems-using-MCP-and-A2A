import json
import uuid
from dataclasses import asdict

from backend.object_model import Usage, Message, UserMessage, SystemMessage, AssistantMessage, ToolMessage, ToolCall


def dict_to_message(message_dict: dict) -> Message:
    """Convert a dictionary to the appropriate Message object."""
    role = message_dict.get('role', '')
    content = message_dict.get('content', '')
    
    if role == 'user':
        return UserMessage(content=content)
    elif role == 'system':
        return SystemMessage(content=content)
    elif role == 'assistant':
        tool_calls = None
        if 'tool_calls' in message_dict and message_dict['tool_calls']:
            tool_calls = []
            for tc in message_dict['tool_calls']:
                # Handle both OpenAI format (with function object) and flat format
                if 'function' in tc:
                    # OpenAI format: {"function": {"name": "...", "arguments": "..."}}
                    name = tc.get('function', {}).get('name', '')
                    arguments = tc.get('function', {}).get('arguments', '')
                else:
                    # Flat format: {"name": "...", "arguments": {...}}
                    name = tc.get('name', '')
                    arguments = tc.get('arguments', '')
                    # Convert dict arguments to JSON string if needed
                    if isinstance(arguments, dict):
                        import json
                        arguments = json.dumps(arguments)
                
                tool_calls.append(ToolCall(
                    id=tc.get('id', ''),
                    name=name,
                    arguments=arguments,
                    required=tc.get('required', [])
                ))
        usage = None
        if 'usage' in message_dict and message_dict['usage']:
            usage_dict = message_dict['usage']
            usage = Usage(
                input_tokens=usage_dict.get('input_tokens', 0),
                output_tokens=usage_dict.get('output_tokens', 0)
            )
        return AssistantMessage(
            content=content,
            tool_calls=tool_calls,
            usage=usage
        )
    elif role == 'tool':
        return ToolMessage(
            content=content,
            name=message_dict.get('name', ''),
            tool_call_id=message_dict.get('tool_call_id', '')
        )
    else:
        # Fallback to base Message
        return Message(content=content, role=role)


class Session:
    def __init__(self, memory_dir: str):
        self.session_id = str(uuid.uuid4())
        self.title = 'Untiled session ~' + self.session_id
        self.messages: list[Message] = []
        self.usage = Usage(0, 0)
        self.memory_dir = memory_dir

    def add_message(self, message: Message):
        """Add a Message object to the session."""
        self.messages.append(message)
        
        # Extract usage from AssistantMessage if present
        if hasattr(message, 'usage') and message.usage:
            self.usage = Usage(
                self.usage.input_tokens + message.usage.input_tokens,
                self.usage.output_tokens + message.usage.output_tokens
            )

    def save(self):
        # Convert Message objects to dictionaries for JSON serialization
        message_dicts = [asdict(msg) for msg in self.messages]
        
        d = dict(session_id=self.session_id,
                 title=self.title,
                 messages=message_dicts,
                 usage=dict(
                    input_tokens=self.usage.input_tokens,
                    output_tokens=self.usage.output_tokens))
        filename = f"{self.memory_dir}/{self.session_id}.json"
        with open(filename, 'w') as f:
            json.dump(d, f, indent=4)

    def load(self, session_id: str):
        """Load session from disk, properly deserializing nested objects"""
        filename = f"{self.memory_dir}/{session_id}.json"
        with open(filename, 'r') as f:
            d = json.load(f)
        self.session_id = d['session_id']
        self.title = d['title']
        
        # Convert message dictionaries back to Message objects
        self.messages = [dict_to_message(msg) for msg in d['messages']]
        
        # Deserialize usage directly to a Usage object
        self.usage = Usage(d['usage']['input_tokens'], d['usage']['output_tokens'])