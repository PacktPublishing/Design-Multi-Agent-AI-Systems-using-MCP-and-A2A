"""Core kubectl functionality for k8s-ai."""

import json
import os
from typing import Dict, List, Any

import sh
from openai import OpenAI


class KubectlExecutor:
    """Handles kubectl command execution and OpenAI integration."""
    
    def __init__(self, context: str = None):
        """Initialize kubectl executor with optional context."""
        self.context = context
        self.client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
        self.model_name = "gpt-4o"
        self.tools = [{
            "type": "function",
            "function": {
                "name": "kubectl",
                "description": "execute a kubectl command against the current k8s cluster",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {
                            "type": "string",
                            "description": (
                                "the kubectl command to execute (without kubectl, just "
                                "the arguments). For example, 'get pods'"
                            ),
                        },
                    },
                    "required": ["cmd"],
                },
            },
        }]
    
    def execute_kubectl(self, cmd: str) -> str:
        """Execute a kubectl command and return the result."""
        cmd_parts = cmd.split()
        if self.context:
            cmd_parts = ['--context', self.context] + cmd_parts
        
        try:
            result = sh.kubectl(cmd_parts)
            return str(result)
        except sh.ErrorReturnCode as e:
            return f"Error: {e.stderr.decode() if e.stderr else str(e)}"
    
    def send_message(self, messages: List[Dict[str, Any]]) -> str:
        """Send messages to OpenAI and handle tool calls."""
        response = self.client.chat.completions.create(
            model=self.model_name, 
            messages=messages, 
            tools=self.tools, 
            tool_choice="auto"
        )
        
        r = response.choices[0].message
        
        if r.tool_calls:
            message = dict(
                role=r.role,
                content=r.content,
                tool_calls=[
                    dict(
                        id=t.id, 
                        type=t.type, 
                        function=dict(name=t.function.name, arguments=t.function.arguments)
                    ) for t in r.tool_calls if t.function
                ]
            )
            messages.append(message)
            
            for t in r.tool_calls:
                if t.function.name == 'kubectl':
                    cmd = json.loads(t.function.arguments)['cmd']
                    result = self.execute_kubectl(cmd)
                    messages.append(dict(
                        tool_call_id=t.id, 
                        role="tool", 
                        name=t.function.name, 
                        content=result
                    ))
            
            return self.send_message(messages)
        
        return r.content.strip()