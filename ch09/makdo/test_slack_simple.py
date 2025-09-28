#!/usr/bin/env python3
"""
Simple Slack integration test
"""

import os
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_slack_simple():
    """Test basic Slack API connectivity"""
    token = os.getenv("AI6_BOT_TOKEN")

    if not token:
        print("❌ No Slack token found")
        return False

    print(f"✅ Token found: {token[:10]}...")

    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: List channels
    print("\n🔍 Testing channel listing...")
    response = requests.get(
        "https://slack.com/api/conversations.list",
        headers=headers,
        params={"types": "public_channel", "limit": 100}
    )

    if response.status_code != 200:
        print(f"❌ API request failed: {response.status_code}")
        return False

    data = response.json()
    if not data.get("ok"):
        print(f"❌ API error: {data.get('error', 'unknown')}")
        return False

    channels = data.get("channels", [])
    print(f"✅ Found {len(channels)} channels")

    # Look for makdo-devops channel
    makdo_channel = None
    for channel in channels:
        if channel.get("name") == "makdo-devops":
            makdo_channel = channel
            break

    if makdo_channel:
        print(f"✅ Found #makdo-devops channel: {makdo_channel['id']}")

        # Test 2: Send a simple message
        print("\n📤 Testing message sending...")
        message_response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json={
                "channel": makdo_channel["id"],
                "text": f"🧪 **Simple Slack Test**\n⏰ Test time: {os.popen('date').read().strip()}\n✅ Direct API integration working!",
                "username": "MAKDO Test Bot"
            }
        )

        if message_response.status_code == 200:
            msg_data = message_response.json()
            if msg_data.get("ok"):
                print("✅ Message sent successfully!")

                # Test 3: Read recent messages
                print("\n📥 Testing message reading...")
                read_response = requests.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers,
                    params={
                        "channel": makdo_channel["id"],
                        "limit": 5
                    }
                )

                if read_response.status_code == 200:
                    read_data = read_response.json()
                    if read_data.get("ok"):
                        messages = read_data.get("messages", [])
                        print(f"✅ Read {len(messages)} recent messages")

                        print("\n🎉 ALL SLACK TESTS PASSED!")
                        print(f"📱 Channel: #makdo-devops ({makdo_channel['id']})")
                        print("🤖 Bot can read and write messages successfully!")
                        return True

        print(f"❌ Message send failed: {message_response.json()}")
        return False
    else:
        print("❌ #makdo-devops channel not found")
        print("Available channels:")
        for channel in channels[:10]:
            print(f"  • #{channel.get('name', 'unknown')}")
        return False

if __name__ == "__main__":
    success = test_slack_simple()
    exit(0 if success else 1)