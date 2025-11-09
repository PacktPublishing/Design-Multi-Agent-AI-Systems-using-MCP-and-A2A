"""Slack channel listing tool"""

import os
import requests
from pathlib import Path
from ai_six.object_model import Tool


class SlackListChannels(Tool):
    """Tool to list Slack channels"""

    def __init__(self, engine=None):
        """Initialize the tool"""
        self.engine = engine

        super().__init__(
            name='slack_list_channels',
            description='List all channels in the Slack workspace',
            parameters=[],
            required=set()
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

    def run(self) -> str:
        """List all channels in the workspace

        Returns:
            List of channels or error message
        """
        bot_token = self._get_token()

        if not bot_token:
            return "❌ AI6_BOT_TOKEN not found"

        url = 'https://slack.com/api/conversations.list'
        headers = {
            'Authorization': f'Bearer {bot_token}'
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            result = response.json()

            if result.get('ok'):
                channels = result.get('channels', [])
                channel_list = [
                    f"#{ch['name']} (member: {ch.get('is_member', False)})"
                    for ch in channels
                ]
                return '\n'.join(channel_list) if channel_list else "No channels found"
            else:
                error = result.get('error', 'unknown_error')
                return f"❌ Failed to list channels: {error}"

        except Exception as e:
            return f"❌ Exception listing channels: {str(e)}"
