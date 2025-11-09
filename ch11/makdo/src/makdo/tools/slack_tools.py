#!/usr/bin/env python3
"""
Regular Python tools for Slack (not MCP) to avoid event loop issues
"""

import os
import requests
from pathlib import Path


def get_slack_token():
    """Get Slack bot token from environment"""
    token = os.getenv('AI6_BOT_TOKEN')

    if not token:
        # Try to load from .env file
        script_path = Path(__file__).resolve()
        # From: .../makdo/src/makdo/tools/slack_tools.py
        # To:   .../makdo/.env
        makdo_root = script_path.parent.parent.parent
        env_file = makdo_root / '.env'

        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith('AI6_BOT_TOKEN='):
                        token = line.split('=', 1)[1].strip()
                        break

    return token


def slack_post_message(channel: str, text: str) -> str:
    """Post a message to a Slack channel

    Args:
        channel: Channel name (e.g., makdo-devops or #makdo-devops)
        text: Message text to post

    Returns:
        Success or error message
    """
    bot_token = get_slack_token()

    if not bot_token:
        return "❌ AI6_BOT_TOKEN not found - Slack posting disabled (this is OK for testing)"

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


def slack_list_channels() -> str:
    """List all channels in the workspace

    Returns:
        List of channels
    """
    bot_token = get_slack_token()

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
