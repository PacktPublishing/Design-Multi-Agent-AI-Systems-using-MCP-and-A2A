#!/usr/bin/env python3
"""Debug script to see what Analyzer returns"""

import sys
import os
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / "git" / "ai-six" / "py"))

from ai_six.agent.agent import Agent
from ai_six.agent.config import Config
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug")

# Start k8s-ai server
k8s_ai_path = Path.home() / "git" / "k8s-ai"
server_process = subprocess.Popen(
    ['python', '-m', 'k8s_ai.server.main', '--context', 'kind-makdo-test',
     '--host', '127.0.0.1', '--port', '9999', '--auth-key', 'test-key'],
    cwd=k8s_ai_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)
time.sleep(2)

# Create coordinator
config = Config.from_file("src/makdo/agents/coordinator.yaml")
coordinator = Agent(config)

logger.info("=" * 80)
logger.info("TESTING ANALYZER")
logger.info("=" * 80)

# Ask coordinator to run analyzer and show us the results
response = coordinator.send_message(
    """
Use the Analyzer agent to check the health of the kind-makdo-test cluster.
After you get the Analyzer's response, repeat it back to me VERBATIM so I can see exactly what the Analyzer said.
Do NOT post to Slack. Just tell me what the Analyzer said.
""",
    coordinator.default_model_id
)

logger.info("\n" + "=" * 80)
logger.info("COORDINATOR'S RESPONSE:")
logger.info("=" * 80)
logger.info(response)

# Check session messages
logger.info("\n" + "=" * 80)
logger.info("LAST FEW SESSION MESSAGES:")
logger.info("=" * 80)
for i, msg in enumerate(coordinator.session.messages[-5:]):
    logger.info(f"\n--- Message {i} ---")
    logger.info(f"Role: {msg.get('role')}")
    content = msg.get('content', '')
    if isinstance(content, str):
        logger.info(f"Content: {content[:1000]}")
    elif isinstance(content, list):
        logger.info(f"Content blocks: {len(content)}")

server_process.terminate()
