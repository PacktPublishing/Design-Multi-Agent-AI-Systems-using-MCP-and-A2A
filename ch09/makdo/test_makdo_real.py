#!/usr/bin/env python3
"""
Real MAKDO E2E Test - Verifies actual multi-agent system with A2A integration
"""

import sys
import os
import time
import subprocess
import requests
import logging
from pathlib import Path

# Add AI-6 to path
sys.path.insert(0, str(Path.home() / "git" / "ai-six" / "py"))

from ai_six.agent.agent import Agent
from ai_six.agent.config import Config
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MAKDO-E2E-Test")


class MAKDOTest:
    def __init__(self):
        self.server_process = None
        self.coordinator = None

    def check_service(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def start_k8s_ai_server(self) -> bool:
        logger.info("🔧 Checking k8s-ai server...")

        if self.check_service("http://localhost:9999/.well-known/agent.json"):
            logger.info("✅ k8s-ai server already running")
            return True

        logger.info("🚀 Starting k8s-ai server...")
        k8s_ai_path = Path.home() / "git" / "k8s-ai"

        try:
            self.server_process = subprocess.Popen(
                ['python', '-m', 'k8s_ai.server.main', '--context', 'kind-k8s-ai',
                 '--host', '127.0.0.1', '--port', '9999'],
                cwd=k8s_ai_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            for i in range(100):  # 10 second timeout
                if self.check_service("http://localhost:9999/.well-known/agent.json"):
                    logger.info("✅ k8s-ai server started")
                    return True
                time.sleep(0.1)
                if self.server_process.poll() is not None:
                    logger.error("❌ k8s-ai server died")
                    return False

            logger.error("❌ k8s-ai server failed to start")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start k8s-ai: {e}")
            return False

    def create_coordinator(self) -> bool:
        logger.info("🤖 Creating MAKDO Coordinator...")

        try:
            config = Config.from_file("src/makdo/agents/coordinator.yaml")
            self.coordinator = Agent(config)

            # Check for A2A tools
            a2a_tools = [name for name in self.coordinator.tool_dict.keys()
                         if name.startswith('kind-k8s-ai_')]

            # Check for agent tools
            agent_tools = [name for name in self.coordinator.tool_dict.keys()
                           if name.startswith('agent_')]

            logger.info(f"✅ Coordinator ready:")
            logger.info(f"   - {len(a2a_tools)} k8s-ai A2A tools")
            logger.info(f"   - {len(agent_tools)} sub-agent tools")

            # Print ALL tool names to debug
            logger.info("All tools:")
            for tool_name in sorted(self.coordinator.tool_dict.keys()):
                # Check if tool name is valid OpenAI pattern
                import re
                if not re.match(r'^[a-zA-Z0-9_-]+$', tool_name):
                    logger.error(f"   ❌ INVALID TOOL NAME: {tool_name}")
                else:
                    logger.info(f"   ✅ {tool_name}")

            if not a2a_tools:
                logger.error("❌ No A2A tools discovered!")
                return False

            if len(agent_tools) < 3:
                logger.error(f"❌ Expected 3 agent tools, found {len(agent_tools)}")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Failed to create coordinator: {e}")
            import traceback
            traceback.print_exc()
            return False

    def test_analyzer_agent(self) -> bool:
        logger.info("🔬 Testing Analyzer agent...")

        try:
            # Call analyzer agent
            analyzer_tool = self.coordinator.tool_dict.get('agent_MAKDO_Analyzer')
            if not analyzer_tool:
                logger.error("❌ Analyzer agent tool not found")
                return False

            result = analyzer_tool.run(
                message="List all pods in the kind-k8s-ai cluster"
            )

            logger.info(f"✅ Analyzer responded: {result[:200]}...")
            return True

        except Exception as e:
            logger.error(f"❌ Analyzer test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_test(self) -> bool:
        logger.info("=" * 60)
        logger.info("🧪 MAKDO REAL E2E TEST")
        logger.info("=" * 60)

        if not self.start_k8s_ai_server():
            return False

        if not self.create_coordinator():
            return False

        if not self.test_analyzer_agent():
            return False

        logger.info("=" * 60)
        logger.info("🎉 TEST PASSED!")
        logger.info("=" * 60)
        return True

    def cleanup(self):
        logger.info("🧹 Cleaning up...")
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()


def main():
    test = MAKDOTest()
    try:
        success = test.run_test()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("⏹️  Interrupted")
        return 1
    except Exception as e:
        logger.error(f"💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        test.cleanup()


if __name__ == "__main__":
    sys.exit(main())
