#!/usr/bin/env python3
"""
E2E Infrastructure Test - Tests the testing infrastructure itself
Verifies failure simulation, Slack integration, and test reporting
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from same directory
import importlib.util
spec = importlib.util.spec_from_file_location("test_makdo_e2e", Path(__file__).parent / "test_makdo_e2e.py")
test_makdo_e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_makdo_e2e)

KubernetesFailureSimulator = test_makdo_e2e.KubernetesFailureSimulator
SlackNotificationVerifier = test_makdo_e2e.SlackNotificationVerifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MAKDO-Infrastructure-Test")

class InfrastructureTest:
    """Test the E2E testing infrastructure components"""

    def __init__(self):
        self.results = {
            "test_type": "infrastructure",
            "start_time": time.time(),
            "tests": {}
        }
        self.failure_simulator = KubernetesFailureSimulator()

        # Setup Slack if token available
        import os
        slack_token = os.getenv("AI6_BOT_TOKEN")
        self.slack_verifier = SlackNotificationVerifier(slack_token) if slack_token else None

    async def test_kubernetes_failure_simulation(self) -> bool:
        """Test that we can create and detect Kubernetes failures"""
        logger.info("Testing Kubernetes failure simulation...")

        try:
            # Setup test environment
            if not self.failure_simulator.setup_test_namespace():
                return False

            # Test each failure scenario
            scenarios = {
                "failing_pod": self.failure_simulator.create_failing_pod,
                "crashloop_pod": self.failure_simulator.create_crashloop_pod,
                "resource_starved": self.failure_simulator.create_resource_starved_pod,
                "unhealthy_service": self.failure_simulator.create_unhealthy_service
            }

            results = {}
            for name, scenario_func in scenarios.items():
                logger.info(f"  Testing scenario: {name}")
                results[name] = scenario_func()
                time.sleep(2)

            success_count = sum(results.values())
            total_count = len(results)
            success = success_count >= (total_count * 0.8)  # 80% success rate

            self.results["tests"]["k8s_failure_simulation"] = {
                "success": success,
                "scenarios": results,
                "success_rate": success_count / total_count
            }

            logger.info(f"  Kubernetes failure simulation: {success_count}/{total_count} scenarios successful")
            return success

        except Exception as e:
            logger.error(f"Kubernetes failure simulation test error: {e}")
            self.results["tests"]["k8s_failure_simulation"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_slack_integration(self) -> bool:
        """Test Slack channel creation and messaging"""
        logger.info("Testing Slack integration...")

        if not self.slack_verifier:
            logger.warning("No Slack token available, skipping Slack tests")
            self.results["tests"]["slack_integration"] = {
                "success": True,
                "skipped": True,
                "reason": "No Slack token available"
            }
            return True

        try:
            # Test channel creation/setup
            channel_setup = self.slack_verifier.channel_id is not None

            # Test sending messages
            test_message = f"🧪 **Infrastructure Test Message**\n⏰ {datetime.now().strftime('%H:%M:%S')}"
            message_sent = self.slack_verifier.send_test_message(test_message)

            # Test message retrieval (wait a bit first)
            time.sleep(3)
            messages = self.slack_verifier.get_recent_messages(limit=10)
            message_received = len(messages) > 0

            success = channel_setup and message_sent and message_received

            self.results["tests"]["slack_integration"] = {
                "success": success,
                "channel_setup": channel_setup,
                "message_sent": message_sent,
                "message_received": message_received,
                "message_count": len(messages)
            }

            logger.info(f"  Slack integration: Setup={channel_setup}, Sent={message_sent}, Received={message_received}")

            if success and self.slack_verifier:
                # Send success notification
                self.slack_verifier.send_test_message(
                    f"✅ **Slack Integration Test Passed!**\n"
                    f"📱 Channel: {self.slack_verifier.channel}\n"
                    f"🤖 Bot can send and receive messages"
                )

            return success

        except Exception as e:
            logger.error(f"Slack integration test error: {e}")
            self.results["tests"]["slack_integration"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_failure_detection_workflow(self) -> bool:
        """Test end-to-end failure detection workflow (without MAKDO)"""
        logger.info("Testing failure detection workflow...")

        try:
            # Create a simple failing pod
            pod_created = self.failure_simulator.create_failing_pod()
            if not pod_created:
                return False

            # Wait for failure to manifest
            logger.info("  Waiting for failure to manifest...")
            time.sleep(15)

            # Check if we can detect the failure using kubectl
            import subprocess
            result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "pods", "-n", self.failure_simulator.namespace,
                "--field-selector=status.phase!=Running",
                "-o", "jsonpath={.items[*].metadata.name}"
            ], capture_output=True, text=True)

            failing_pods = result.stdout.strip().split() if result.stdout.strip() else []
            failure_detected = len(failing_pods) > 0

            # Get pod events for more details
            events_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "events", "-n", self.failure_simulator.namespace,
                "--field-selector=type=Warning",
                "-o", "jsonpath={.items[*].reason}"
            ], capture_output=True, text=True)

            warning_events = events_result.stdout.strip().split() if events_result.stdout.strip() else []
            expected_events = ["Failed", "ErrImagePull", "ImagePullBackOff"]
            relevant_events = [e for e in warning_events if any(exp in e for exp in expected_events)]

            success = failure_detected and len(relevant_events) > 0

            self.results["tests"]["failure_detection_workflow"] = {
                "success": success,
                "pod_created": pod_created,
                "failure_detected": failure_detected,
                "failing_pods": failing_pods,
                "relevant_events": relevant_events
            }

            logger.info(f"  Failure detection: Pods={len(failing_pods)}, Events={len(relevant_events)}")

            # Notify via Slack if available
            if self.slack_verifier and success:
                self.slack_verifier.send_test_message(
                    f"🔍 **Failure Detection Test Passed!**\n"
                    f"💥 Detected {len(failing_pods)} failing pods\n"
                    f"⚠️ Found {len(relevant_events)} warning events\n"
                    f"📊 Events: {', '.join(relevant_events[:3])}"
                )

            return success

        except Exception as e:
            logger.error(f"Failure detection workflow test error: {e}")
            self.results["tests"]["failure_detection_workflow"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_cleanup_procedures(self) -> bool:
        """Test that cleanup procedures work correctly"""
        logger.info("Testing cleanup procedures...")

        try:
            # Test cleanup
            self.failure_simulator.cleanup()

            # Verify cleanup worked
            import subprocess
            result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "namespace", self.failure_simulator.namespace
            ], capture_output=True, text=True)

            cleanup_successful = result.returncode != 0  # Namespace should be gone

            self.results["tests"]["cleanup_procedures"] = {
                "success": cleanup_successful,
                "namespace_deleted": cleanup_successful
            }

            logger.info(f"  Cleanup procedures: {'✅ Success' if cleanup_successful else '❌ Failed'}")
            return cleanup_successful

        except Exception as e:
            logger.error(f"Cleanup procedures test error: {e}")
            self.results["tests"]["cleanup_procedures"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def run_infrastructure_tests(self) -> Dict[str, Any]:
        """Run all infrastructure tests"""
        logger.info("🏗️ Starting MAKDO Infrastructure Tests")

        if self.slack_verifier:
            self.slack_verifier.send_test_message(
                f"🏗️ **MAKDO Infrastructure Test Starting**\n"
                f"🧪 Testing E2E infrastructure components\n"
                f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}"
            )

        tests = [
            ("Kubernetes Failure Simulation", self.test_kubernetes_failure_simulation),
            ("Slack Integration", self.test_slack_integration),
            ("Failure Detection Workflow", self.test_failure_detection_workflow),
            ("Cleanup Procedures", self.test_cleanup_procedures),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            logger.info(f"\n--- Running: {test_name} ---")
            try:
                if await test_func():
                    passed += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                logger.error(f"💥 {test_name}: EXCEPTION - {e}")

        # Calculate results
        self.results["end_time"] = time.time()
        self.results["duration"] = self.results["end_time"] - self.results["start_time"]
        self.results["summary"] = {
            "total_tests": total,
            "passed_tests": passed,
            "success_rate": passed / total,
            "overall_success": passed >= (total * 0.8)  # 80% pass rate
        }

        # Save results
        results_file = Path("tests/e2e/infrastructure_results.json")
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        # Send final Slack notification
        if self.slack_verifier:
            success_icon = "🎉" if self.results["summary"]["overall_success"] else "😞"
            self.slack_verifier.send_test_message(
                f"{success_icon} **Infrastructure Test Complete**\n"
                f"📊 Passed: {passed}/{total} tests\n"
                f"⏱️ Duration: {self.results['duration']:.1f}s\n"
                f"🎯 Overall: {'SUCCESS' if self.results['summary']['overall_success'] else 'FAILURE'}"
            )

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("MAKDO Infrastructure Test Results")
        logger.info(f"{'='*60}")
        logger.info(f"Tests passed: {passed}/{total}")
        logger.info(f"Success rate: {passed/total:.1%}")
        logger.info(f"Duration: {self.results['duration']:.1f}s")

        if self.results["summary"]["overall_success"]:
            logger.info("🎉 Overall: SUCCESS")
        else:
            logger.info("😞 Overall: FAILURE")

        logger.info(f"Detailed results: {results_file}")

        return self.results

async def main():
    """Main test runner"""
    tester = InfrastructureTest()
    results = await tester.run_infrastructure_tests()

    return 0 if results["summary"]["overall_success"] else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))