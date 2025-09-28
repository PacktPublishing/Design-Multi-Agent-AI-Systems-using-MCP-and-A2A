import os
from functools import partial

import pathology.path
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

from slack_sdk.errors import SlackApiError

from . import utils

script_dir = pathology.path.Path.script_dir()

# Try to load environment variables from .env file in the same directory as this script
env_file_path = os.path.join(script_dir, ".env")
if os.path.exists(env_file_path):
    load_dotenv(env_file_path)
    print(f"Loaded environment variables from {env_file_path}")
else:
    print(f"Warning: No .env file found at {env_file_path}")

app_token = os.environ.get("AI6_APP_TOKEN")
bot_token = os.environ.get("AI6_BOT_TOKEN")

# Initializes your AI-6 app with your bot token and socket mode handler
app = App(token=bot_token)
bot_user_id = app.client.auth_test()["user_id"]

last_message = ""
latest_ts = None
ai6_channels = {}

# Load configuration from TOML file
config_path = str((script_dir / 'config.toml').resolve())

# Initialize engines with separate session storage per channel
engines = {}

def get_or_create_engine(channel_id):
    """Get an existing engine for a channel or create a new one."""
    if channel_id not in engines:
        # Create a channel-specific engine using the Slack utility function
        engines[channel_id] = utils.create_channel_engine(
            base_config_path=config_path,
            channel_id=channel_id,
            env_file_path=env_file_path
        )

    return engines[channel_id]


def handle_tool_call(client, channel, name, args, result):
    """Handle a tool call from the AI-6 engine."""
    # Post the tool call result as a message
    try:
        client.chat_postMessage(
            channel=channel,
            thread_ts=latest_ts,
            text=f"_Tool call: `{name}` {', '.join(args.values()) if args else ''}_\n{result}"
        )
    except SlackApiError as e:
        print(f"Error posting tool call result: {e}")

@app.event("message")
def handle_message(message, say, ack, client):
    """Handle all messages in channels."""
    global last_message, latest_ts
    ack()  # Acknowledge ASAP
    
    text = message.get("text")
    
    # Skip if the message is empty or from a bot
    if not text or message.get("bot_id"):
        return

    mention_bot = f"<@{bot_user_id}>" in text
    channel_id = message['channel']
    ai6_channel = channel_id in ai6_channels

    # Ignore messages that don't mention the bot and are not a special AI-6 channel
    if not mention_bot and not ai6_channel:
        return

    engine = get_or_create_engine(channel_id)
    
    # Create a tool call handler for this channel
    channel_tool_call_handler = partial(handle_tool_call, client, channel_id)
    
    # Process the message with the AI-6 engine
    try:
        # Post an initial empty message that we'll update
        result = client.chat_postMessage(
            channel=channel_id,
            text="..."
        )
    
        latest_ts = result["ts"]
        last_message = ""
    
        # Define a callback function to handle streaming chunks
        def handle_chunk(chunk):
            global last_message
            last_message += chunk
        
            try:
                # Update the message with the new content
                client.chat_update(
                    channel=channel_id,
                    ts=latest_ts,
                    text=last_message
                )
            except SlackApiError as e:
                print(f"Error updating message: {e}")
    
        # Stream the message to the AI-6 engine
        response = engine.stream_message(
            text, 
            engine.default_model_id, 
            on_chunk_func=handle_chunk,
            on_tool_call_func=channel_tool_call_handler
        )
    
    except Exception as e:
        print(f"I encountered an error: {str(e)}")


def join_channel(client):
    """Join the first AI-6 channel if not a member already
    
    Return the channel id
    
    If there are no AI-6 channel raise an exception
    """
    all_channels = client.conversations_list()['channels']
    ai6_channels.update({c['id']: c for c in all_channels if c['name'].startswith('ai-6-')})
    if not ai6_channels:
        return

    channel_id = list(ai6_channels.keys())[0]
    channel = ai6_channels[channel_id]

    # Join channel if not a member already
    if not channel['is_member']:
        try:
            client.conversations_join(channel=channel_id)
        except Exception as e:
            print(f"Error joining channel {channel_id}: {e}")

    return channel


def leave_channels(client):
    """Leave all the channels
    """
    channels = (c for c in client.conversations_list()['channels'] if c['is_member'])
    for c in channels:
        client.chat_postMessage(
            channel=c['id'],
            text=f"Leaving channel #{c['name']}"
        )
        client.conversations_leave(channel=c['id'])


def main():
    """Main entry point for the Slack app"""
    channel = join_channel(app.client)
    if channel is not None:
        print(f'Joined {channel["name"]}')

    try:
        # Run the Slack app
        SocketModeHandler(app, app_token).start()
    except KeyboardInterrupt:
        print("Ctrl+C detected.")
    except Exception as e:
        print(f"Unhandled exception: {e}")
    finally:
        leave_channels(app.client)


if __name__ == "__main__":
    main()
