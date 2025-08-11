import asyncio
import sys
import json
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from openai import OpenAI


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai_client = OpenAI()

    async def connect_to_server(self, server_path: str):
        """Connect to an MCP server"""
        is_python = server_path.endswith('.py')
        is_js = server_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools  # Correct way, no .choices[0]
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        """Process a query using OpenAI and available tools"""
        messages = [
            {"role": "system", "content": "You are an intelligent assistant. You will execute tasks as prompted."},
            {"role": "user", "content": query}
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # First LLM call
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=available_tools,
            max_tokens=250,
            temperature=0.2,
        )

        final_text = []
        tool_results = []

        choice = response.choices[0].message

        if choice.content:
            final_text.append(choice.content)

        if choice.tool_calls:
            for tool_call in choice.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Execute the tool
                result = await self.session.call_tool(tool_name, tool_args)
                tool_results.append({"call": tool_name, "result": result})

                final_text.append(f"[Called tool {tool_name} with args {tool_args}]")

                # Continue conversation with tool result
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()]  # echo the tool call
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content
                })

                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=1000,
                )

                choice = response.choices[0].message
                if choice.content:
                    final_text.append(choice.content)

        return "\n".join(final_text)

    async def run(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                print("\n" + response)

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """Cleanup resources"""
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.run()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())