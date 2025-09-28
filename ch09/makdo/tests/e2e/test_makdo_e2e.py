#!/usr/bin/env python3
"""
End-to-End Test Suite for MAKDO
Simulates real Kubernetes failures and verifies complete MAKDO workflow
"""

import asyncio
import json
import logging
import subprocess
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests
import os
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class KubernetesFailureSimulator:
    """Simulates various Kubernetes failure modes for testing"""

    def __init__(self, context: str = "kind-makdo-test"):
        self.context = context
        self.namespace = "makdo-test"
        self.created_resources = []

    def setup_test_namespace(self):
        """Create test namespace and basic resources"""
        try:
            subprocess.run([
                "kubectl", "--context", self.context,
                "create", "namespace", self.namespace
            ], check=False, capture_output=True)

            # Label namespace for easy cleanup
            subprocess.run([
                "kubectl", "--context", self.context,
                "label", "namespace", self.namespace,
                "test=makdo-e2e"
            ], check=True, capture_output=True)

            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to setup test namespace: {e}")
            return False

    def create_failing_pod(self) -> bool:
        """Create a pod that will fail to start"""
        pod_yaml = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "failing-app",
                "namespace": self.namespace,
                "labels": {"app": "failing-app", "test": "makdo-e2e"}
            },
            "spec": {
                "containers": [{
                    "name": "app",
                    "image": "nonexistent-image:latest",
                    "imagePullPolicy": "Always"
                }],
                "restartPolicy": "Never"
            }
        }

        return self._apply_resource("failing-pod", pod_yaml)

    def create_crashloop_pod(self) -> bool:
        """Create a pod that crashes in a loop"""
        pod_yaml = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "crashloop-app",
                "namespace": self.namespace,
                "labels": {"app": "crashloop-app", "test": "makdo-e2e"}
            },
            "spec": {
                "containers": [{
                    "name": "app",
                    "image": "busybox",
                    "command": ["sh", "-c", "exit 1"]
                }],
                "restartPolicy": "Always"
            }
        }

        return self._apply_resource("crashloop-pod", pod_yaml)

    def create_resource_starved_pod(self) -> bool:
        """Create a pod that can't be scheduled due to resource constraints"""
        pod_yaml = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": "resource-starved",
                "namespace": self.namespace,
                "labels": {"app": "resource-starved", "test": "makdo-e2e"}
            },
            "spec": {
                "containers": [{
                    "name": "app",
                    "image": "nginx",
                    "resources": {
                        "requests": {
                            "cpu": "1000",  # Unrealistic CPU request
                            "memory": "100Gi"  # Unrealistic memory request
                        }
                    }
                }]
            }
        }

        return self._apply_resource("resource-starved-pod", pod_yaml)

    def create_unhealthy_service(self) -> bool:
        """Create a service with failing health checks"""
        # Deployment with failing health checks
        deployment_yaml = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "unhealthy-service",
                "namespace": self.namespace,
                "labels": {"test": "makdo-e2e"}
            },
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": "unhealthy"}},
                "template": {
                    "metadata": {"labels": {"app": "unhealthy"}},
                    "spec": {
                        "containers": [{
                            "name": "app",
                            "image": "nginx",
                            "ports": [{"containerPort": 80}],
                            "readinessProbe": {
                                "httpGet": {"path": "/nonexistent", "port": 80},
                                "initialDelaySeconds": 5,
                                "periodSeconds": 5
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/nonexistent", "port": 80},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 10
                            }
                        }]
                    }
                }
            }
        }

        # Service
        service_yaml = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": "unhealthy-service",
                "namespace": self.namespace,
                "labels": {"test": "makdo-e2e"}
            },
            "spec": {
                "selector": {"app": "unhealthy"},
                "ports": [{"port": 80, "targetPort": 80}]
            }
        }

        return (self._apply_resource("unhealthy-deployment", deployment_yaml) and
                self._apply_resource("unhealthy-service", service_yaml))

    def simulate_node_pressure(self) -> bool:
        """Create many pods to simulate node pressure"""
        for i in range(10):
            pod_yaml = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": f"pressure-pod-{i}",
                    "namespace": self.namespace,
                    "labels": {"app": "pressure-test", "test": "makdo-e2e"}
                },
                "spec": {
                    "containers": [{
                        "name": "app",
                        "image": "nginx",
                        "resources": {
                            "requests": {"memory": "100Mi", "cpu": "100m"},
                            "limits": {"memory": "200Mi", "cpu": "200m"}
                        }
                    }]
                }
            }

            if not self._apply_resource(f"pressure-pod-{i}", pod_yaml):
                return False

        return True

    def _apply_resource(self, name: str, resource: Dict[str, Any]) -> bool:
        """Apply a Kubernetes resource and track it for cleanup"""
        try:
            temp_file = Path(f"/tmp/makdo-test-{name}.yaml")
            with open(temp_file, 'w') as f:
                yaml.dump(resource, f)

            result = subprocess.run([
                "kubectl", "--context", self.context,
                "apply", "-f", str(temp_file)
            ], check=True, capture_output=True, text=True)

            self.created_resources.append({
                "name": name,
                "kind": resource["kind"],
                "metadata": resource["metadata"],
                "file": temp_file
            })

            logging.info(f"Created {resource['kind']}: {resource['metadata']['name']}")
            temp_file.unlink()  # Clean up temp file
            return True

        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to apply {name}: {e.stderr}")
            return False

    def cleanup(self):
        """Clean up all created test resources"""
        logging.info("Cleaning up test resources...")

        try:
            # Delete namespace (cascades to all resources)
            subprocess.run([
                "kubectl", "--context", self.context,
                "delete", "namespace", self.namespace,
                "--wait=false"
            ], check=False, capture_output=True)

            logging.info(f"Deleted test namespace: {self.namespace}")

        except Exception as e:
            logging.error(f"Cleanup error: {e}")

        # Clean up temp files
        for resource in self.created_resources:
            if resource.get("file") and resource["file"].exists():
                resource["file"].unlink()


class SlackNotificationVerifier:
    """Verifies Slack notifications are sent correctly"""

    def __init__(self, bot_token: str, channel: str = "#makdo-devops"):
        self.bot_token = bot_token
        self.channel = channel
        self.base_url = "https://slack.com/api"
        self.headers = {"Authorization": f"Bearer {bot_token}"}
        self.test_start_time = datetime.now()
        self.channel_id = None

        # Ensure channel exists and bot is a member
        self._setup_channel()

    def get_recent_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent messages from the channel"""
        try:
            # Convert channel name to ID if needed
            channel_id = self._get_channel_id()
            if not channel_id:
                return []

            # Get messages since test started
            timestamp = self.test_start_time.timestamp()

            response = requests.get(
                f"{self.base_url}/conversations.history",
                headers=self.headers,
                params={
                    "channel": channel_id,
                    "limit": limit,
                    "oldest": timestamp
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data.get("messages", [])

            logging.error(f"Failed to get messages: {response.text}")
            return []

        except Exception as e:
            logging.error(f"Error getting Slack messages: {e}")
            return []

    def verify_alert_sent(self, alert_type: str, cluster: str, timeout: int = 60) -> bool:
        """Verify that a specific alert was sent to Slack"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = self.get_recent_messages()

            for message in messages:
                text = message.get("text", "").lower()
                if (alert_type.lower() in text and
                    cluster.lower() in text and
                    "makdo" in text.lower()):
                    logging.info(f"Found {alert_type} alert for {cluster}")
                    return True

            time.sleep(5)  # Check every 5 seconds

        logging.warning(f"No {alert_type} alert found for {cluster} within {timeout}s")
        return False

    def verify_resolution_sent(self, issue_type: str, timeout: int = 60) -> bool:
        """Verify that a resolution notification was sent"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = self.get_recent_messages()

            for message in messages:
                text = message.get("text", "").lower()
                if ("resolved" in text or "fixed" in text) and issue_type.lower() in text:
                    logging.info(f"Found resolution notification for {issue_type}")
                    return True

            time.sleep(5)

        return False

    def get_makdo_messages(self) -> List[str]:
        """Get all MAKDO-related messages for analysis"""
        messages = self.get_recent_messages()
        makdo_messages = []

        for message in messages:
            text = message.get("text", "")
            if "makdo" in text.lower() or "coordinator" in text.lower():
                makdo_messages.append(text)

        return makdo_messages

    def _setup_channel(self):
        """Setup channel - find existing or create if doesn't exist"""
        try:
            logging.info(f"Setting up Slack channel: {self.channel}")

            # First, try to find existing channel
            channel_id = self._find_channel()

            if channel_id:
                self.channel_id = channel_id
                # Ensure bot is a member
                self._join_channel()
                logging.info(f"✅ Channel setup complete: {self.channel} (ID: {channel_id})")
                return

            # Channel doesn't exist, try to create it
            logging.info(f"Channel {self.channel} not found, attempting to create...")
            channel_id = self._create_channel()

            if channel_id:
                self.channel_id = channel_id
                # Ensure bot is a member
                self._join_channel()
                logging.info(f"✅ Channel created and setup complete: {self.channel} (ID: {channel_id})")
            else:
                logging.warning(f"⚠️ Could not create channel {self.channel} - bot may not have permissions")
                logging.info("This is okay for testing - Slack messages will be skipped")

        except Exception as e:
            logging.warning(f"Channel setup warning: {e}")
            logging.info("Continuing test without Slack integration")

    def _find_channel(self) -> Optional[str]:
        """Find channel by name, return channel ID if found"""
        try:
            # Check public channels first
            response = requests.get(
                f"{self.base_url}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel", "limit": 1000}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channel_name = self.channel.lstrip("#")
                    for channel in data.get("channels", []):
                        if channel.get("name") == channel_name:
                            logging.info(f"Found existing channel: {self.channel} (ID: {channel.get('id')})")
                            return channel.get("id")

            # If not found in public channels, check private channels
            response = requests.get(
                f"{self.base_url}/conversations.list",
                headers=self.headers,
                params={"types": "private_channel", "limit": 1000}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channel_name = self.channel.lstrip("#")
                    for channel in data.get("channels", []):
                        if channel.get("name") == channel_name:
                            logging.info(f"Found existing private channel: {self.channel} (ID: {channel.get('id')})")
                            return channel.get("id")

            logging.warning(f"Channel {self.channel} not found in public or private channels")
            return None

        except Exception as e:
            logging.error(f"Error finding channel: {e}")
            return None

    def _create_channel(self) -> Optional[str]:
        """Create a new Slack channel"""
        try:
            channel_name = self.channel.lstrip("#")

            response = requests.post(
                f"{self.base_url}/conversations.create",
                headers=self.headers,
                json={
                    "name": channel_name,
                    "is_private": False
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channel_id = data.get("channel", {}).get("id")
                    logging.info(f"✅ Created channel: {self.channel} (ID: {channel_id})")

                    # Set channel purpose/topic
                    self._set_channel_purpose(channel_id)

                    return channel_id
                else:
                    error = data.get("error", "Unknown error")
                    if error == "name_taken":
                        # Channel exists but we couldn't find it, try again
                        logging.info("Channel exists, retrying find...")
                        return self._find_channel()
                    else:
                        logging.error(f"Failed to create channel: {error}")

            return None

        except Exception as e:
            logging.error(f"Error creating channel: {e}")
            return None

    def _set_channel_purpose(self, channel_id: str):
        """Set channel purpose/description"""
        try:
            purpose = "MAKDO E2E Test Channel - Multi-Agent Kubernetes DevOps notifications and alerts"

            requests.post(
                f"{self.base_url}/conversations.setPurpose",
                headers=self.headers,
                json={
                    "channel": channel_id,
                    "purpose": purpose
                }
            )

            # Also set topic
            topic = "🤖 MAKDO Alerts | 🔍 Cluster Health | ⚠️ Issues & Fixes"

            requests.post(
                f"{self.base_url}/conversations.setTopic",
                headers=self.headers,
                json={
                    "channel": channel_id,
                    "topic": topic
                }
            )

        except Exception as e:
            logging.warning(f"Could not set channel purpose: {e}")

    def _join_channel(self):
        """Ensure bot is a member of the channel"""
        if not self.channel_id:
            return

        try:
            response = requests.post(
                f"{self.base_url}/conversations.join",
                headers=self.headers,
                json={"channel": self.channel_id}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logging.info(f"✅ Bot joined channel: {self.channel}")
                else:
                    error = data.get("error", "Unknown error")
                    if error in ["already_in_channel", "is_archived"]:
                        logging.info(f"Bot already in channel or channel archived: {error}")
                    else:
                        logging.warning(f"Could not join channel: {error}")
            else:
                logging.warning(f"Join channel request failed: {response.status_code}")

        except Exception as e:
            logging.warning(f"Error joining channel: {e}")

    def _get_channel_id(self) -> Optional[str]:
        """Get channel ID (for backward compatibility)"""
        if self.channel_id:
            return self.channel_id
        return self._find_channel()

    def send_test_message(self, message: str = None) -> bool:
        """Send a test message to verify channel setup"""
        if not message:
            message = f"🧪 MAKDO E2E Test Started at {datetime.now().strftime('%H:%M:%S')}\n" \
                     f"Testing multi-agent Kubernetes DevOps system..."

        try:
            if not self.channel_id:
                logging.error("No channel ID available for test message")
                return False

            response = requests.post(
                f"{self.base_url}/chat.postMessage",
                headers=self.headers,
                json={
                    "channel": self.channel_id,
                    "text": message,
                    "username": "MAKDO E2E Test"
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logging.info("✅ Test message sent successfully")
                    return True
                else:
                    logging.error(f"Test message failed: {data.get('error')}")

            return False

        except Exception as e:
            logging.error(f"Error sending test message: {e}")
            return False


class MAKDOTester:
    """Main E2E test orchestrator"""

    def __init__(self):
        self.failure_simulator = KubernetesFailureSimulator()
        self.slack_verifier = None
        self.makdo_process = None
        self.k8s_ai_process = None

        # Load configuration
        self.load_config()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tests/e2e/makdo_e2e.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("MAKDO-E2E")

    def load_config(self):
        """Load test configuration from environment and config files"""
        # Load environment
        from dotenv import load_dotenv
        load_dotenv()

        # Setup Slack verifier if token available
        slack_token = os.getenv("AI6_BOT_TOKEN")
        if slack_token:
            self.slack_verifier = SlackNotificationVerifier(slack_token)

    async def setup_environment(self) -> bool:
        """Setup test environment - clusters, namespaces, etc."""
        self.logger.info("Setting up E2E test environment...")

        # Setup Slack channel and send test start message
        if self.slack_verifier:
            self.logger.info("Setting up Slack channel...")
            success = self.slack_verifier.send_test_message(
                f"🚀 **MAKDO E2E Test Starting**\n"
                f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🎯 Testing: Multi-Agent Kubernetes DevOps System\n"
                f"📊 Will simulate failures and verify detection/remediation"
            )
            if not success:
                self.logger.warning("Could not send Slack test message, but continuing...")

        # Verify clusters exist
        clusters = ["kind-k8s-ai", "kind-makdo-test"]
        for cluster in clusters:
            if not self._verify_cluster_exists(cluster):
                self.logger.error(f"Cluster {cluster} not found - creating...")
                if not self._create_test_cluster(cluster):
                    return False

        # Setup test namespace
        if not self.failure_simulator.setup_test_namespace():
            return False

        # Start k8s-ai server if not running
        if not self._is_k8s_ai_running():
            self.logger.info("Starting k8s-ai server...")
            self.k8s_ai_process = subprocess.Popen([
                "uv", "run", "k8s-ai-server",
                "--context", "kind-k8s-ai",
                "--port", "9999"
            ], cwd="/Users/gigi/git/k8s-ai")
            time.sleep(10)  # Wait for server to start

        # Send environment setup completion message
        if self.slack_verifier:
            self.slack_verifier.send_test_message(
                f"✅ **Environment Setup Complete**\n"
                f"🖥️ Clusters: kind-k8s-ai, kind-makdo-test\n"
                f"🔧 k8s-ai server: Running on localhost:9999\n"
                f"📦 Test namespace: {self.failure_simulator.namespace}\n"
                f"🎬 Ready to simulate failures!"
            )

        return True

    async def run_failure_scenarios(self) -> Dict[str, bool]:
        """Run all failure scenarios and track results"""
        self.logger.info("Running failure scenarios...")

        scenarios = {
            "failing_pod": self.failure_simulator.create_failing_pod,
            "crashloop_pod": self.failure_simulator.create_crashloop_pod,
            "resource_starved": self.failure_simulator.create_resource_starved_pod,
            "unhealthy_service": self.failure_simulator.create_unhealthy_service,
            "node_pressure": self.failure_simulator.simulate_node_pressure,
        }

        results = {}
        for name, scenario_func in scenarios.items():
            self.logger.info(f"Running scenario: {name}")
            results[name] = scenario_func()
            time.sleep(5)  # Space out scenario creation

        # Wait for failures to manifest
        self.logger.info("Waiting for failures to manifest...")
        time.sleep(30)

        # Notify about failure scenarios completion
        if hasattr(self, 'slack_verifier') and self.slack_verifier:
            successful_scenarios = sum(results.values())
            total_scenarios = len(results)
            self.slack_verifier.send_test_message(
                f"💥 **Failure Scenarios Created**\n"
                f"✅ Successful: {successful_scenarios}/{total_scenarios}\n"
                f"📋 Scenarios: {', '.join(results.keys())}\n"
                f"⏳ Waiting for MAKDO to detect and respond..."
            )

        return results

    async def start_makdo_system(self) -> bool:
        """Start MAKDO system for testing"""
        self.logger.info("Starting MAKDO system...")

        try:
            self.makdo_process = subprocess.Popen([
                "uv", "run", "makdo"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Give MAKDO time to initialize
            time.sleep(15)

            # Check if process is still running
            if self.makdo_process.poll() is None:
                self.logger.info("MAKDO system started successfully")
                return True
            else:
                stdout, stderr = self.makdo_process.communicate()
                self.logger.error(f"MAKDO failed to start: {stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to start MAKDO: {e}")
            return False

    async def verify_detection_and_notification(self) -> Dict[str, bool]:
        """Verify MAKDO detects issues and sends notifications"""
        self.logger.info("Verifying detection and notifications...")

        verification_results = {}

        if not self.slack_verifier:
            self.logger.warning("Slack verifier not available - skipping notification tests")
            return verification_results

        # Wait for MAKDO to run health checks and detect issues
        self.logger.info("Waiting for MAKDO health check cycle...")
        time.sleep(90)  # Wait for health check cycle

        # Verify different types of alerts
        alert_tests = [
            ("pod failure", "kind-makdo-test"),
            ("crashloop", "kind-makdo-test"),
            ("scheduling", "kind-makdo-test"),
            ("readiness", "kind-makdo-test"),
        ]

        for alert_type, cluster in alert_tests:
            result = self.slack_verifier.verify_alert_sent(alert_type, cluster, timeout=120)
            verification_results[f"{alert_type}_alert"] = result

        return verification_results

    async def verify_remediation_actions(self) -> Dict[str, bool]:
        """Verify MAKDO attempts appropriate remediation"""
        self.logger.info("Verifying remediation actions...")

        remediation_results = {}

        # Check for remediation attempts in logs/Slack
        # This would involve checking if MAKDO:
        # 1. Identifies fixable issues
        # 2. Requests approval for destructive actions
        # 3. Applies safe fixes
        # 4. Reports results

        time.sleep(60)  # Wait for remediation cycle

        if self.slack_verifier:
            makdo_messages = self.slack_verifier.get_makdo_messages()

            # Look for remediation keywords in messages
            remediation_keywords = ["fixing", "resolved", "applying", "restarting"]
            found_remediation = any(
                any(keyword in msg.lower() for keyword in remediation_keywords)
                for msg in makdo_messages
            )

            remediation_results["remediation_attempted"] = found_remediation

        return remediation_results

    async def run_complete_test(self) -> Dict[str, Any]:
        """Run complete E2E test suite"""
        self.logger.info("Starting MAKDO E2E Test Suite")

        test_results = {
            "start_time": datetime.now().isoformat(),
            "environment_setup": False,
            "failure_scenarios": {},
            "makdo_startup": False,
            "detection_and_notification": {},
            "remediation": {},
            "success": False
        }

        try:
            # 1. Setup environment
            test_results["environment_setup"] = await self.setup_environment()
            if not test_results["environment_setup"]:
                return test_results

            # 2. Create failure scenarios
            test_results["failure_scenarios"] = await self.run_failure_scenarios()

            # 3. Start MAKDO
            test_results["makdo_startup"] = await self.start_makdo_system()
            if not test_results["makdo_startup"]:
                return test_results

            # 4. Verify detection and notifications
            test_results["detection_and_notification"] = await self.verify_detection_and_notification()

            # 5. Verify remediation attempts
            test_results["remediation"] = await self.verify_remediation_actions()

            # 6. Calculate overall success
            test_results["success"] = self._calculate_overall_success(test_results)
            test_results["end_time"] = datetime.now().isoformat()

            # Send completion message to Slack
            if self.slack_verifier:
                self._send_completion_message(test_results)

            return test_results

        except Exception as e:
            self.logger.error(f"Test suite failed: {e}")
            test_results["error"] = str(e)
            return test_results

        finally:
            await self.cleanup()

    def _calculate_overall_success(self, results: Dict[str, Any]) -> bool:
        """Calculate overall test success based on individual results"""
        # Minimum requirements for success:
        # 1. Environment setup successful
        # 2. At least 80% of failure scenarios created
        # 3. MAKDO started successfully
        # 4. At least some detection/notification occurred

        if not results["environment_setup"] or not results["makdo_startup"]:
            return False

        # Check failure scenario success rate
        scenario_results = list(results["failure_scenarios"].values())
        scenario_success_rate = sum(scenario_results) / len(scenario_results) if scenario_results else 0

        # Check detection success
        detection_results = list(results["detection_and_notification"].values())
        detection_success = any(detection_results) if detection_results else False

        return scenario_success_rate >= 0.8 and detection_success

    def _send_completion_message(self, results: Dict[str, Any]):
        """Send test completion message to Slack"""
        try:
            success_icon = "🎉" if results["success"] else "😞"
            status = "SUCCESS" if results["success"] else "FAILURE"

            # Count results
            scenario_count = len(results.get("failure_scenarios", {}))
            scenario_success = sum(results.get("failure_scenarios", {}).values())

            detection_count = len(results.get("detection_and_notification", {}))
            detection_success = sum(results.get("detection_and_notification", {}).values())

            remediation_count = len(results.get("remediation", {}))
            remediation_success = sum(results.get("remediation", {}).values())

            message = (
                f"{success_icon} **MAKDO E2E Test Complete: {status}**\n"
                f"\n📊 **Results Summary:**\n"
                f"• Environment Setup: {'✅' if results.get('environment_setup') else '❌'}\n"
                f"• MAKDO Startup: {'✅' if results.get('makdo_startup') else '❌'}\n"
                f"• Failure Scenarios: {scenario_success}/{scenario_count} ✅\n"
                f"• Detection & Alerts: {detection_success}/{detection_count} ✅\n"
                f"• Remediation Actions: {remediation_success}/{remediation_count} ✅\n"
                f"\n⏰ **Duration:** {(datetime.now() - self.slack_verifier.test_start_time).total_seconds():.1f}s\n"
                f"📅 **Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            self.slack_verifier.send_test_message(message)

        except Exception as e:
            self.logger.warning(f"Could not send completion message: {e}")

    def _verify_cluster_exists(self, cluster_name: str) -> bool:
        """Check if Kubernetes cluster exists"""
        try:
            result = subprocess.run([
                "kubectl", "config", "get-contexts", cluster_name
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _create_test_cluster(self, cluster_name: str) -> bool:
        """Create a kind cluster for testing"""
        try:
            cluster_short_name = cluster_name.replace("kind-", "")
            subprocess.run([
                "kind", "create", "cluster", "--name", cluster_short_name
            ], check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create cluster {cluster_name}: {e}")
            return False

    def _is_k8s_ai_running(self) -> bool:
        """Check if k8s-ai server is running"""
        try:
            response = requests.get("http://localhost:9999/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    async def cleanup(self):
        """Clean up test environment"""
        self.logger.info("Cleaning up test environment...")

        # Stop MAKDO process
        if self.makdo_process and self.makdo_process.poll() is None:
            self.makdo_process.terminate()
            try:
                self.makdo_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.makdo_process.kill()

        # Stop k8s-ai process if we started it
        if self.k8s_ai_process and self.k8s_ai_process.poll() is None:
            self.k8s_ai_process.terminate()
            try:
                self.k8s_ai_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.k8s_ai_process.kill()

        # Clean up Kubernetes resources
        self.failure_simulator.cleanup()

        self.logger.info("Cleanup completed")


async def main():
    """Main test runner"""
    tester = MAKDOTester()
    results = await tester.run_complete_test()

    # Save results
    results_file = Path("tests/e2e/results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary
    print("\n" + "="*60)
    print("MAKDO E2E Test Results")
    print("="*60)
    print(f"Overall Success: {'✅ PASS' if results['success'] else '❌ FAIL'}")
    print(f"Environment Setup: {'✅' if results['environment_setup'] else '❌'}")
    print(f"MAKDO Startup: {'✅' if results['makdo_startup'] else '❌'}")

    print(f"\nFailure Scenarios:")
    for scenario, success in results['failure_scenarios'].items():
        print(f"  {scenario}: {'✅' if success else '❌'}")

    print(f"\nDetection & Notification:")
    for test, success in results['detection_and_notification'].items():
        print(f"  {test}: {'✅' if success else '❌'}")

    print(f"\nRemediation:")
    for test, success in results['remediation'].items():
        print(f"  {test}: {'✅' if success else '❌'}")

    print(f"\nDetailed results saved to: {results_file}")

    return 0 if results['success'] else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))