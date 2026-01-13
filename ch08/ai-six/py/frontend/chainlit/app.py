import argparse
import sys
from types import SimpleNamespace

# Fix engineio packet limit before importing chainlit
from engineio.payload import Payload
Payload.max_decode_packets = 500

import chainlit as cl
from chainlit.cli import run_chainlit

import pathology.path

from frontend.common import agent_utils

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description='AI-6 Chainlit Frontend')
    parser.add_argument('--streaming-mode', type=str, choices=['true', 'false'], default='true',
                       help='Enable/disable streaming responses (default: true)')
    # Only parse known args to avoid conflicts with chainlit's arguments
    args, unknown = parser.parse_known_args()
    
    # Convert string to boolean
    args.streaming_mode = args.streaming_mode.lower() == 'true'
    
    # Preserve our arguments for potential module reloads
    preserved_args = []
    if any('--streaming-mode' in arg for arg in sys.argv):
        # Find the original streaming-mode argument and preserve it
        for i, arg in enumerate(sys.argv):
            if arg.startswith('--streaming-mode'):
                if '=' in arg:
                    preserved_args.append(arg)
                elif i + 1 < len(sys.argv):
                    preserved_args.extend([arg, sys.argv[i + 1]])
                break
    
    # Put back both unknown args and our preserved args so chainlit can process unknown ones
    sys.argv[1:] = unknown + preserved_args
    return args

# Parse arguments before setting up the app
cli_args = parse_args()

script_dir = pathology.path.Path.script_dir()

# Load the agent from YAML configuration
config_path = str((script_dir / "config.yaml").resolve())

# Create agent from configuration file
# Environment variables will be automatically interpolated by Config.from_file
agent, agent_config = agent_utils.create_from_config(config_path)

app_config = SimpleNamespace(
    selected_model=agent.default_model_id,
    available_models=list(agent.model_provider_map.keys()),
    enabled_tools={tool: True for tool in agent.tool_dict},
    use_streaming=cli_args.streaming_mode,
)


TOOL_PREFIX = "tool:"


async def setup_settings():
    model_select = cl.input_widget.Select(
        id="model",
        label="LLM Model",
        values=app_config.available_models,
        initial_value=app_config.selected_model,
        initial_index=app_config.available_models.index(app_config.selected_model),
    )
    tool_switches = [
        cl.input_widget.Switch(
            id=f"{TOOL_PREFIX}{tool_name}",
            label=f"Tool: {tool_name}",
            initial=tool_value,
        )
        for tool_name, tool_value in app_config.enabled_tools.items()
    ]

    await cl.ChatSettings([model_select] + tool_switches).send()


@cl.on_settings_update
async def on_settings_update(new_settings):
    app_config.selected_model = new_settings["model"]
    for k, v in new_settings.items():
        if k.startswith(TOOL_PREFIX):
            tool_name = k.replace(TOOL_PREFIX, "")
            app_config.enabled_tools[tool_name] = v


@cl.on_chat_start
async def on_chat_start():
    await setup_settings()
    streaming_status = "streaming" if app_config.use_streaming else "non-streaming"
    await cl.Message(content=f"AI-6 is ready ({streaming_status} mode). Let's go 🚀!").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Process user messages and generate responses."""
    enabled_tool_ids = [k for k, v in app_config.enabled_tools.items() if v]
    
    if app_config.use_streaming:
        # Streaming mode
        msg = cl.Message(content="")
        await msg.send()

        # Define a callback function to handle streaming chunks
        async def on_chunk(chunk: str):
            # Use the Chainlit built-in streaming method
            await msg.stream_token(chunk)

        # Stream the response
        try:
            agent.stream_message(
                message.content,
                app_config.selected_model,
                on_chunk_func=lambda chunk: cl.run_sync(on_chunk(chunk)),
                available_tool_ids=enabled_tool_ids,
            )
            # Mark the message as complete
            await msg.update()
        except Exception as e:
            await cl.Message(content=f"Error: {str(e)}").send()
    else:
        # Non-streaming mode
        try:
            # Temporarily filter tools in the agent for non-streaming
            original_tool_dict = agent.tool_dict
            if enabled_tool_ids:
                agent.tool_dict = {
                    k: v for k, v in agent.tool_dict.items() if k in enabled_tool_ids
                }
            
            response = agent.send_message(
                message.content,
                app_config.selected_model,
                None,  # on_tool_call_func
            )
            await cl.Message(content=response).send()
            
        except Exception as e:
            await cl.Message(content=f"Error: {str(e)}").send()
        finally:
            # Restore original tool dict
            agent.tool_dict = original_tool_dict


if __name__ == "__main__":
    target = str(script_dir / "app.py")
    run_chainlit(target)
