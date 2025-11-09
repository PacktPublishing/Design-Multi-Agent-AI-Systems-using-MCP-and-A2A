"""Slack message posting tool"""

import os
import requests
from pathlib import Path
from ai_six.object_model import Tool, Parameter


class SlackPostMessage(Tool):
    """Tool to post messages to Slack channels"""

    def __init__(self, engine=None):
        """Initialize the tool"""
        self.engine = engine

        super().__init__(
            name='slack_post_message',
            description='Post a message to a Slack channel',
            parameters=[
                Parameter('channel', 'string', 'Channel name (e.g., makdo-devops or #makdo-devops)'),
                Parameter('text', 'string', 'Message text to post')
            ],
            required={'channel', 'text'}
        )

    def _get_token(self):
        """Get Slack bot token from environment"""
        token = os.getenv('AI6_BOT_TOKEN')

        if not token:
            script_path = Path(__file__).resolve()
            makdo_root = script_path.parent.parent.parent.parent
            env_file = makdo_root / '.env'

            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('AI6_BOT_TOKEN='):
                            token = line.split('=', 1)[1].strip()
                            break

        return token

    def run(self, channel: str, text: str) -> str:
        """Post a message to a Slack channel

        Args:
            channel: Channel name
            text: Message text

        Returns:
            Success or error message
        """
        bot_token = self._get_token()

        if not bot_token:
            return "❌ AI6_BOT_TOKEN not found - Slack posting disabled"

        # Normalize channel name
        if not channel.startswith('#'):
            channel = f'#{channel}'

        url = 'https://slack.com/api/chat.postMessage'
        headers = {
            'Authorization': f'Bearer {bot_token}',
            'Content-Type': 'application/json; charset=utf-8'
        }
        data = {
            'channel': channel,
            'text': text
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            result = response.json()

            if result.get('ok'):
                return f"✅ Message posted to {channel}"
            else:
                error = result.get('error', 'unknown_error')
                return f"❌ Failed to post to {channel}: {error}"

        except Exception as e:
            return f"❌ Exception posting to Slack: {str(e)}"
