#!/usr/bin/env python3
"""
MAKDO Full Workflow E2E Test
Creates real cluster problems, then tests the full agent workflow:
1. Create problems in cluster
2. Coordinator invokes Analyzer to detect issues
3. Coordinator notifies Slack about issues
4. Coordinator invokes Fixer to remediate
5. Coordinator notifies Slack about resolution
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

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MAKDO-Full-Workflow")


class KubernetesFailureSimulator:
    """Creates real Kubernetes failures for testing"""

    def __init__(self, context: str = "kind-k8s-ai"):
        self.context = context
        self.created_resources = []

    def create_crashloop_pod(self) -> bool:
        """Create a pod that will crashloop"""
        logger.info("💥 Creating crashloop pod...")

        yaml = """
apiVersion: v1
kind: Pod
metadata:
  name: crashloop-test
  namespace: default
spec:
  containers:
  - name: crash
    image: busybox
    command: ["sh", "-c", "exit 1"]
  restartPolicy: Always
"""

        try:
            # Write YAML to temp file
            with open('/tmp/crashloop-pod.yaml', 'w') as f:
                f.write(yaml)

            # Apply the pod
            result = subprocess.run(
                ['kubectl', '--context', self.context, 'apply', '-f', '/tmp/crashloop-pod.yaml'],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                self.created_resources.append(('pod', 'default', 'crashloop-test'))
                logger.info("✅ Crashloop pod created")
                # Wait a bit for it to start crashing
                time.sleep(5)
                return True
            else:
                logger.error(f"❌ Failed to create crashloop pod: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Error creating crashloop pod: {e}")
            return False

    def create_failing_deployment(self) -> bool:
        """Create a deployment with bad image"""
        logger.info("💥 Creating failing deployment...")

        yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: failing-app
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: failing-app
  template:
    metadata:
      labels:
        app: failing-app
    spec:
      containers:
      - name: app
        image: nonexistent/badimage:latest
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
                self.created_resources.append(('deployment', 'default', 'failing-app'))
                logger.info("✅ Failing deployment created")
                time.sleep(5)
                return True
            else:
                logger.error(f"❌ Failed to create deployment: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"❌ Error creating deployment: {e}")
            return False

    def cleanup(self):
        """Clean up all created resources"""
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


class MAKDOWorkflowTest:
    """Test full MAKDO workflow with real agent coordination"""

    def __init__(self):
        self.server_process = None
        self.coordinator = None
        self.failure_sim = KubernetesFailureSimulator()

    def check_service(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def start_k8s_ai_server(self) -> bool:
        logger.info("🔧 Starting k8s-ai server...")

        if self.check_service("http://localhost:9999/.well-known/agent.json"):
            logger.info("✅ k8s-ai server already running")
            return True

        k8s_ai_path = Path.home() / "git" / "k8s-ai"

        try:
            self.server_process = subprocess.Popen(
                ['python', '-m', 'k8s_ai.server.main', '--context', 'kind-k8s-ai',
                 '--host', '127.0.0.1', '--port', '9999'],
                cwd=k8s_ai_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )

            for i in range(100):
                if self.check_service("http://localhost:9999/.well-known/agent.json"):
                    logger.info("✅ k8s-ai server started")
                    return True
                time.sleep(0.1)
                if self.server_process.poll() is not None:
                    return False

            return False

        except Exception as e:
            logger.error(f"❌ Failed to start k8s-ai: {e}")
            return False

    def create_coordinator(self) -> bool:
        logger.info("🤖 Creating MAKDO Coordinator...")

        try:
            config = Config.from_file("src/makdo/agents/coordinator.yaml")
            self.coordinator = Agent(config)

            a2a_tools = [n for n in self.coordinator.tool_dict.keys() if n.startswith('kind-k8s-ai_')]
            agent_tools = [n for n in self.coordinator.tool_dict.keys() if n.startswith('agent_')]

            logger.info(f"✅ Coordinator ready: {len(a2a_tools)} A2A tools, {len(agent_tools)} agent tools")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create coordinator: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_cluster_problems(self) -> bool:
        logger.info("\n" + "="*60)
        logger.info("STEP 1: Creating cluster problems")
        logger.info("="*60)

        success = True
        success = self.failure_sim.create_crashloop_pod() and success
        success = self.failure_sim.create_failing_deployment() and success

        if success:
            logger.info("✅ Cluster problems created")
        else:
            logger.warning("⚠️  Some problems failed to create")

        return success

    def test_full_workflow(self) -> bool:
        """Test the complete MAKDO workflow"""
        logger.info("\n" + "="*60)
        logger.info("STEP 2: Running MAKDO Coordinator Workflow")
        logger.info("="*60)

        try:
            # Coordinator orchestrates the full workflow
            workflow_message = """
Please execute the following MAKDO workflow:

1. Use the Analyzer agent to check the health of the kind-k8s-ai cluster
2. Based on the analysis, notify the Slack agent about any critical issues found
3. If there are issues that can be auto-remediated, ask the Fixer agent to fix them
4. After fixes are applied, verify the results and notify Slack again with the outcome

This is a complete end-to-end test of MAKDO's autonomous DevOps capabilities.
"""

            logger.info("📋 Sending workflow request to Coordinator...")
            logger.info("\n" + "-"*60)

            response = self.coordinator.send_message(
                workflow_message,
                self.coordinator.default_model_id
            )

            logger.info("-"*60)
            logger.info("🤖 Coordinator Response:")
            logger.info("-"*60)
            logger.info(response)
            logger.info("-"*60 + "\n")

            # Verify workflow execution
            workflow_success = True

            # Check if Analyzer was called
            if "agent_MAKDO_Analyzer" not in str(self.coordinator.session.messages):
                logger.warning("⚠️  Analyzer agent was not invoked")
                workflow_success = False
            else:
                logger.info("✅ Analyzer agent was invoked")

            # Check if Slack was called
            if "agent_MAKDO_Slack_Bot" not in str(self.coordinator.session.messages):
                logger.warning("⚠️  Slack agent was not invoked")
                workflow_success = False
            else:
                logger.info("✅ Slack agent was invoked")

            # Check if Fixer was called
            if "agent_MAKDO_Fixer" not in str(self.coordinator.session.messages):
                logger.warning("⚠️  Fixer agent was not invoked")
                workflow_success = False
            else:
                logger.info("✅ Fixer agent was invoked")

            return workflow_success

        except Exception as e:
            logger.error(f"❌ Workflow test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_test(self) -> bool:
        logger.info("=" * 60)
        logger.info("🧪 MAKDO FULL WORKFLOW E2E TEST")
        logger.info("=" * 60)

        if not self.start_k8s_ai_server():
            return False

        if not self.create_coordinator():
            return False

        if not self.create_cluster_problems():
            return False

        # Give problems time to manifest
        logger.info("⏳ Waiting for problems to manifest...")
        time.sleep(10)

        if not self.test_full_workflow():
            return False

        logger.info("\n" + "=" * 60)
        logger.info("🎉 FULL WORKFLOW TEST PASSED!")
        logger.info("=" * 60)
        logger.info("\nWorkflow demonstrated:")
        logger.info("  1. ✅ Real cluster problems created")
        logger.info("  2. ✅ Coordinator invoked Analyzer agent")
        logger.info("  3. ✅ Coordinator notified Slack agent")
        logger.info("  4. ✅ Coordinator invoked Fixer agent")
        logger.info("  5. ✅ Complete autonomous DevOps workflow")

        return True

    def cleanup(self):
        logger.info("\n🧹 Final cleanup...")
        self.failure_sim.cleanup()
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()


def main():
    test = MAKDOWorkflowTest()
    try:
        success = test.run_test()
        return 0 if success else 1
    except KeyboardInterrupt:
        logger.info("\n⏹️  Test interrupted")
        return 1
    except Exception as e:
        logger.error(f"\n💥 Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        test.cleanup()


if __name__ == "__main__":
    sys.exit(main())
