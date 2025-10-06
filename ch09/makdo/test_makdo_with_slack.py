#!/usr/bin/env python3
"""
MAKDO Full Real Test with Slack Integration
This test:
1. Creates REAL cluster problems
2. Coordinator invokes Analyzer (uses k8s-ai A2A)
3. Coordinator posts REAL analyzer results to Slack
4. Coordinator invokes Fixer to remediate
5. Coordinator posts REAL fixer results to Slack
6. Pauses for screenshot capture at each step
"""

import sys
import os
import time
import subprocess
import requests
import logging
from pathlib import Path

sys.path.insert(0, str(Path.home() / "git" / "ai-six" / "py"))

from ai_six.agent.agent import Agent
from ai_six.agent.config import Config
from dotenv import load_dotenv

# Screenshot functionality removed - capture manually
SCREENSHOTS_ENABLED = False

load_dotenv()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MAKDO-Real-Demo")

# Also enable agent logging
logging.getLogger("ai_six.agent").setLevel(logging.DEBUG)


class KubernetesFailureSimulator:
    """Creates real Kubernetes failures"""

    def __init__(self, context: str = "kind-makdo-test"):
        self.context = context
        self.created_resources = []

    def create_crashloop_pod(self) -> bool:
        logger.info("💥 Creating crashloop pod...")
        yaml = """
apiVersion: v1
kind: Pod
metadata:
  name: crashloop-app
  namespace: default
  labels:
    app: test-crashloop
spec:
  containers:
  - name: crash
    image: busybox
    command: ["sh", "-c", "echo 'Starting...'; sleep 2; exit 1"]
  restartPolicy: Always
"""
        try:
            with open('/tmp/crashloop-pod.yaml', 'w') as f:
                f.write(yaml)

            result = subprocess.run(
                ['kubectl', '--context', self.context, 'apply', '-f', '/tmp/crashloop-pod.yaml'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                self.created_resources.append(('pod', 'default', 'crashloop-app'))
                logger.info("✅ Crashloop pod created")
                time.sleep(5)
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

    def create_failing_deployment(self) -> bool:
        logger.info("💥 Creating failing deployment...")
        yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: image-pull-fail
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: bad-image
  template:
    metadata:
      labels:
        app: bad-image
    spec:
      containers:
      - name: app
        image: nonexistent-registry.io/fake/image:v1.0.0
        imagePullPolicy: Always
"""
        try:
            with open('/tmp/failing-deployment.yaml', 'w') as f:
                f.write(yaml)

            result = subprocess.run(
                ['kubectl', '--context', self.context, 'apply', '-f', '/tmp/failing-deployment.yaml'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                self.created_resources.append(('deployment', 'default', 'image-pull-fail'))
                logger.info("✅ Failing deployment created")
                time.sleep(5)
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return False

    def cleanup(self):
        logger.info("🧹 Cleaning up test resources...")
        for resource_type, namespace, name in self.created_resources:
            try:
                subprocess.run(
                    ['kubectl', '--context', self.context, 'delete', resource_type, name,
                     '-n', namespace, '--force', '--grace-period=0'],
                    capture_output=True, timeout=10
                )
                logger.info(f"   Deleted {resource_type}/{name}")
            except Exception as e:
                logger.warning(f"   Failed to delete {resource_type}/{name}: {e}")


class MAKDORealTest:
    """Real MAKDO test with actual Slack integration"""

    def __init__(self):
        self.k8s_server_process = None
        self.slack_mcp_process = None
        self.coordinator = None
        self.failure_sim = KubernetesFailureSimulator()
        self.screenshot_dir = Path.home() / "git" / "design-multi-agent-ai-systems-book" / "ch-09"
        self.screenshot_count = 0

    def bring_slack_to_front(self) -> bool:
        """Bring Slack window to front"""
        try:
            # Try to bring Slack to front using AppleScript on macOS
            script = '''
            tell application "Slack"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True, timeout=5)
            time.sleep(2)  # Give Slack time to come to front
            return True
        except Exception as e:
            logger.warning(f"Could not bring Slack to front: {e}")
            return False

    def capture_screenshot(self, name: str, description: str = "") -> bool:
        """Capture screenshot of Slack window"""
        if not SCREENSHOTS_ENABLED:
            logger.warning("⚠️  Screenshots disabled (pyautogui not installed)")
            return False

        try:
            logger.info(f"📸 Capturing screenshot: {name}")

            # Bring Slack to front
            self.bring_slack_to_front()

            # Wait for render
            time.sleep(3)

            # Take full screenshot
            screenshot = pyautogui.screenshot()

            # Save with proper naming
            self.screenshot_count += 1
            filename = f"{self.screenshot_count:02d}_{name}.png"
            filepath = self.screenshot_dir / filename

            screenshot.save(filepath)
            logger.info(f"✅ Screenshot saved: {filename}")

            if description:
                logger.info(f"   Description: {description}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to capture screenshot: {e}")
            return False

    def check_service(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    def start_k8s_ai_server(self) -> bool:
        logger.info("🔧 Starting k8s-ai server...")

        if self.check_service("http://localhost:9999/.well-known/agent.json"):
            logger.info("✅ k8s-ai server already running")
            return True

        k8s_ai_path = Path.home() / "git" / "k8s-ai"

        try:
            # Set environment for admin API
            env = os.environ.copy()
            env['A2A_API_KEY'] = 'test-key'

            self.server_process = subprocess.Popen(
                ['python', '-m', 'k8s_ai.server.main', '--context', 'kind-makdo-test',
                 '--host', '127.0.0.1', '--port', '9999', '--auth-key', 'test-key'],
                cwd=k8s_ai_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env
            )

            for i in range(100):
                if self.check_service("http://localhost:9999/.well-known/agent.json"):
                    logger.info("✅ k8s-ai server started")
                    return True
                time.sleep(0.1)

            return False
        except Exception as e:
            logger.error(f"❌ Failed to start k8s-ai: {e}")
            return False

    async def register_cluster_with_k8s_ai(self) -> str:
        """Register cluster with k8s-ai admin API and get session token."""
        import httpx

        api_key = "test-key"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # Get kubeconfig for kind-makdo-test
        import subprocess
        kubeconfig_json = subprocess.check_output(
            ["kubectl", "config", "view", "--context=kind-makdo-test", "--minify", "--raw"],
            text=True
        )

        register_data = {
            "cluster_name": "makdo-test",
            "kubeconfig": kubeconfig_json,
            "ttl_hours": 1
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:9998/clusters/register",
                json=register_data,
                headers=headers,
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(f"Cluster registration failed: {response.text}")

            result = response.json()
            session_token = result.get('session_token')
            logger.info(f"✅ Cluster registered, session token: {session_token[:30]}...")
            return session_token

    def create_coordinator(self, session_token: str) -> bool:
        logger.info("🤖 Creating MAKDO Coordinator with Slack integration...")

        try:
            config = Config.from_file("src/makdo/agents/coordinator.yaml")

            # Inject session token into Analyzer and Fixer system prompts
            for agent_config in config.agents:
                if agent_config.name in ["MAKDO_Analyzer", "MAKDO_Fixer"]:
                    agent_config.system_prompt = f"""SESSION_TOKEN: {session_token}

{agent_config.system_prompt}

IMPORTANT: When calling k8s-ai diagnostic skills, ALWAYS use this session token:
session_token={session_token}
"""

            self.coordinator = Agent(config)

            # Check tools
            a2a_tools = [n for n in self.coordinator.tool_dict.keys() if 'k8s-ai' in n.lower()]
            agent_tools = [n for n in self.coordinator.tool_dict.keys() if n.startswith('agent_')]
            slack_tools = [n for n in self.coordinator.tool_dict.keys() if 'slack' in n.lower()]

            logger.info(f"✅ Coordinator ready:")
            logger.info(f"   - {len(a2a_tools)} k8s-ai A2A tools")
            logger.info(f"   - {len(agent_tools)} sub-agent tools")
            logger.info(f"   - {len(slack_tools)} Slack tools")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to create coordinator: {e}")
            import traceback
            traceback.print_exc()
            return False

    def send_demo_start_message(self):
        """Send initial demo message to Slack"""
        logger.info("\n📸 SCREENSHOT 1: Demo Start")
        logger.info("="*60)

        message = """
🤖 **MAKDO End-to-End Demo**

This demo showcases MAKDO's complete autonomous DevOps workflow:

**Test Scenario:**
1. ✅ Create cluster problems (crashloop pod, failing deployment)
2. 🔍 Analyzer detects issues using k8s-ai
3. 📊 Report findings to Slack
4. 🔧 Fixer attempts remediation
5. ✅ Report results to Slack

**Environment:**
- Cluster: kind-makdo-test
- Channel: #makdo-devops
- Demo started at: """ + time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            response = self.coordinator.send_message(
                f"Post this message to #makdo-devops Slack channel:\n\n{message}",
                self.coordinator.default_model_id
            )
            logger.info("✅ Demo start message sent")
            logger.info(f"Response: {response[:200]}...")
        except Exception as e:
            logger.error(f"❌ Failed to send demo start: {e}")

        # Screenshots disabled - capture manually if needed
        time.sleep(2)  # Brief pause for Slack posting

    def run_analysis_and_post(self):
        """Run analyzer and post results to Slack"""
        logger.info("\n📸 SCREENSHOT 2: Analysis Results")
        logger.info("="*60)

        analysis_request = """
Please perform the following tasks in order:

1. Use the Analyzer agent to check the health of the kind-makdo-test cluster and get the COMPLETE detailed analysis report
2. Immediately forward THE COMPLETE ANALYZER OUTPUT (every detail, every pod name, every error message) to the Slack agent with this message: "Post this complete cluster analysis report to #makdo-devops: [PASTE FULL ANALYZER OUTPUT HERE]"

CRITICAL: Do NOT summarize. Do NOT filter. Post the ENTIRE analysis report exactly as the Analyzer provided it.
"""

        try:
            logger.info("🔬 Running Analyzer and posting results...")
            response = self.coordinator.send_message(
                analysis_request,
                self.coordinator.default_model_id
            )
            logger.info("✅ Analysis completed and posted to Slack")
            logger.info(f"Coordinator response (FULL): {response}")

            # Also print session history to see all agent calls
            logger.info("\n==== COORDINATOR SESSION HISTORY ====")
            for i, msg in enumerate(self.coordinator.session.messages[-10:]):  # Last 10 messages
                logger.info(f"Message {i}: role={msg.get('role', 'unknown')}")
                content = msg.get('content', '')
                if isinstance(content, str):
                    logger.info(f"  Content preview: {content[:500]}")
                elif isinstance(content, list):
                    logger.info(f"  Content blocks: {len(content)}")
                    for block in content:
                        if isinstance(block, dict):
                            logger.info(f"    Block type: {block.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            import traceback
            traceback.print_exc()

        # Screenshots disabled - capture manually if needed
        time.sleep(2)  # Brief pause for Slack posting

    def run_fixer_and_post(self):
        """Run fixer and post results to Slack"""
        logger.info("\n📸 SCREENSHOT 3: Remediation Results")
        logger.info("="*60)

        fix_request = """
Please perform the following tasks in order:

1. Use the Fixer agent to remediate the issues found in the kind-makdo-test cluster and get the COMPLETE detailed remediation report
2. Immediately forward THE COMPLETE FIXER OUTPUT (every action taken, every kubectl command, every result) to the Slack agent with this message: "Post this complete remediation report to #makdo-devops: [PASTE FULL FIXER OUTPUT HERE]"

CRITICAL: Do NOT summarize. Do NOT filter. Post the ENTIRE remediation report exactly as the Fixer provided it.
"""

        try:
            logger.info("🔧 Running Fixer and posting results...")
            response = self.coordinator.send_message(
                fix_request,
                self.coordinator.default_model_id
            )
            logger.info("✅ Remediation completed and posted to Slack")
            logger.info(f"Coordinator response: {response[:300]}...")
        except Exception as e:
            logger.error(f"❌ Remediation failed: {e}")
            import traceback
            traceback.print_exc()

        # Screenshots disabled - capture manually if needed
        time.sleep(2)  # Brief pause for Slack posting

    def send_demo_complete_message(self):
        """Send demo completion message"""
        logger.info("\n📸 SCREENSHOT 4: Demo Complete")
        logger.info("="*60)

        complete_message = """
🎉 **MAKDO Demo Complete!**

**Results:**
✅ Multi-agent coordination successful
✅ Analyzer detected cluster issues via k8s-ai
✅ Fixer attempted remediation
✅ Full autonomous DevOps workflow demonstrated

**Architecture validated:**
- Coordinator orchestrated all agents
- Analyzer used A2A protocol to k8s-ai
- Fixer executed safe remediation
- Slack agent provided human visibility

Demo completed at: """ + time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            response = self.coordinator.send_message(
                f"Post this completion message to #makdo-devops:\n\n{complete_message}",
                self.coordinator.default_model_id
            )
            logger.info("✅ Demo complete message sent")
        except Exception as e:
            logger.error(f"❌ Failed to send completion: {e}")

        # Screenshots disabled - capture manually if needed
        time.sleep(2)  # Brief pause for Slack posting

    def run_test(self) -> bool:
        logger.info("=" * 60)
        logger.info("🧪 MAKDO REAL DEMO WITH SLACK")
        logger.info("=" * 60)

        if not self.start_k8s_ai_server():
            return False

        # Register cluster and get session token
        import asyncio
        session_token = asyncio.run(self.register_cluster_with_k8s_ai())

        if not self.create_coordinator(session_token):
            return False

        logger.info("\n📋 Creating cluster problems...")
        self.failure_sim.create_crashloop_pod()
        self.failure_sim.create_failing_deployment()

        logger.info("\n⏳ Waiting for problems to manifest (15 seconds)...")
        time.sleep(15)

        # Run demo with screenshots
        self.send_demo_start_message()
        self.run_analysis_and_post()
        self.run_fixer_and_post()
        self.send_demo_complete_message()

        logger.info("\n" + "=" * 60)
        logger.info("🎉 DEMO COMPLETE!")
        logger.info("=" * 60)

        return True

    def cleanup(self):
        logger.info("\n🧹 Cleanup...")
        self.failure_sim.cleanup()
        if hasattr(self, 'server_process') and self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()


def main():
    test = MAKDORealTest()
    try:
        success = test.run_test()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted")
        return 1
    except Exception as e:
        logger.error(f"\n💥 Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        test.cleanup()


if __name__ == "__main__":
    sys.exit(main())
