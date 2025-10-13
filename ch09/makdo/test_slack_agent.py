#!/usr/bin/env python3
"""Test Slack Bot agent independently"""

import asyncio
import logging
from ai_six.agent.agent import Agent
from ai_six.agent.config import Config
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("slack-test")

def test_slack_agent():
    """Test the Slack Bot agent independently"""
    load_dotenv()

    logger.info("Creating Slack Bot agent...")

    # Create minimal config for Slack Bot
    import os
    config_dict = {
        "name": "MAKDO_Slack_Bot_Test",
        "description": "Test Slack Bot agent",
        "default_model_id": "gpt-4o",
        "tools_dirs": [],
        "mcp_tools_dirs": ["src/makdo/mcp_tools"],
        "system_prompt": "You are a Slack bot. Post messages to #makdo-devops channel.",
        "provider_config": {
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY")
            }
        }
    }

    try:
        config = Config(**config_dict)
        agent = Agent(config)
        logger.info(f"✅ Agent created with {len(agent.tool_dict)} tools")

        # List available tools
        logger.info("Available tools:")
        for tool_name in agent.tool_dict.keys():
            logger.info(f"  - {tool_name}")

        # Try to send a test message
        logger.info("\nTesting message posting...")
        response = agent.send_message(
            "Post a test message to #makdo-devops saying: 'MAKDO Slack Bot test - system operational'"
        )

        logger.info(f"\n✅ Agent response:\n{response}")
        return True

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_slack_agent()
    exit(0 if success else 1)
