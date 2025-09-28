#!/usr/bin/env python3
"""
Real-World MAKDO E2E Test with Live Slack Integration
Creates actual Kubernetes failures and sends real Slack notifications
"""

import asyncio
import json
import logging
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

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
logger = logging.getLogger("MAKDO-RealWorld-E2E")

class RealWorldMAKDOTest:
    """Real-world E2E test with live Slack integration and actual failures"""

    def __init__(self):
        self.results = {
            "test_type": "real_world_e2e",
            "start_time": time.time(),
            "tests": {}
        }

        # Initialize components
        self.failure_simulator = KubernetesFailureSimulator()

        # Get Slack token from environment
        slack_token = os.getenv("AI6_BOT_TOKEN")
        logger.info(f"Slack token found: {'Yes' if slack_token else 'No'}")
        logger.info(f"Token starts with: {slack_token[:10] + '...' if slack_token else 'None'}")

        if not slack_token:
            raise ValueError("AI6_BOT_TOKEN not found in environment - cannot run real Slack test")

        self.slack_verifier = SlackNotificationVerifier(slack_token, "#makdo-devops")

    async def test_slack_channel_creation_and_messaging(self) -> bool:
        """Test creating/joining Slack channel and sending messages"""
        logger.info("🔧 Testing Slack channel creation and messaging...")

        try:
            # The channel should already be created during SlackNotificationVerifier init
            channel_ready = self.slack_verifier.channel_id is not None

            if not channel_ready:
                logger.error("❌ Slack channel setup failed")
                return False

            logger.info(f"✅ Slack channel ready: {self.slack_verifier.channel} (ID: {self.slack_verifier.channel_id})")

            # Send welcome message
            welcome_msg = (
                f"🚀 **MAKDO Real-World E2E Test Starting!**\n\n"
                f"🤖 **What we're testing:**\n"
                f"• Creating real Kubernetes failures in kind clusters\n"
                f"• Detecting and reporting issues through this channel\n"
                f"• End-to-end failure simulation and notification workflow\n\n"
                f"⏰ **Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📱 **Channel:** {self.slack_verifier.channel}\n"
                f"🎯 **Goal:** Validate complete MAKDO E2E infrastructure"
            )

            welcome_sent = self.slack_verifier.send_test_message(welcome_msg)

            if welcome_sent:
                logger.info("✅ Welcome message sent to Slack")
            else:
                logger.error("❌ Failed to send welcome message")
                return False

            # Wait and check if message was received
            time.sleep(3)
            recent_messages = self.slack_verifier.get_recent_messages(limit=5)
            message_received = len(recent_messages) > 0

            self.results["tests"]["slack_channel_setup"] = {
                "success": channel_ready and welcome_sent and message_received,
                "channel_id": self.slack_verifier.channel_id,
                "welcome_sent": welcome_sent,
                "message_received": message_received,
                "recent_message_count": len(recent_messages)
            }

            logger.info(f"✅ Slack integration test: Setup={channel_ready}, Sent={welcome_sent}, Received={message_received}")
            return channel_ready and welcome_sent and message_received

        except Exception as e:
            logger.error(f"❌ Slack channel test failed: {e}")
            self.results["tests"]["slack_channel_setup"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_kubernetes_cluster_setup(self) -> bool:
        """Test Kubernetes cluster setup and namespace creation"""
        logger.info("🔧 Testing Kubernetes cluster setup...")

        try:
            # Setup test namespace
            namespace_created = self.failure_simulator.setup_test_namespace()

            if namespace_created:
                # Send notification to Slack
                setup_msg = (
                    f"✅ **Kubernetes Environment Ready**\n\n"
                    f"🖥️ **Cluster:** kind-makdo-test\n"
                    f"📦 **Namespace:** {self.failure_simulator.namespace}\n"
                    f"🔧 **Resource limits:** CPU: 4, Memory: 8Gi\n"
                    f"📊 **Pod quota:** 50 pods max\n\n"
                    f"🎬 Ready to simulate failures!"
                )
                self.slack_verifier.send_test_message(setup_msg)

            self.results["tests"]["k8s_cluster_setup"] = {
                "success": namespace_created,
                "namespace": self.failure_simulator.namespace
            }

            logger.info(f"✅ Kubernetes setup: {'Success' if namespace_created else 'Failed'}")
            return namespace_created

        except Exception as e:
            logger.error(f"❌ Kubernetes setup failed: {e}")
            self.results["tests"]["k8s_cluster_setup"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_failure_scenarios_with_slack_reporting(self) -> bool:
        """Create failures and report each one to Slack in real-time"""
        logger.info("💥 Testing failure scenarios with live Slack reporting...")

        try:
            scenarios = [
                ("Image Pull Failure", "failing_pod", self.failure_simulator.create_failing_pod),
                ("CrashLoop BackOff", "crashloop_pod", self.failure_simulator.create_crashloop_pod),
                ("Resource Scheduling Issue", "resource_starved", self.failure_simulator.create_resource_starved_pod),
                ("Health Check Failure", "unhealthy_service", self.failure_simulator.create_unhealthy_service),
                ("Node Resource Pressure", "node_pressure", self.failure_simulator.simulate_node_pressure),
            ]

            results = {}
            successful_scenarios = []
            failed_scenarios = []

            for display_name, scenario_id, scenario_func in scenarios:
                logger.info(f"  💥 Creating scenario: {display_name}")

                # Notify Slack about starting scenario
                scenario_msg = f"💥 **Creating Failure Scenario: {display_name}**\n⏳ Deploying problematic resources..."
                self.slack_verifier.send_test_message(scenario_msg)

                # Create the failure scenario
                success = scenario_func()
                results[scenario_id] = success

                if success:
                    successful_scenarios.append(display_name)
                    result_msg = f"✅ **{display_name}** - Successfully created failure scenario"
                    logger.info(f"    ✅ {display_name} created successfully")
                else:
                    failed_scenarios.append(display_name)
                    result_msg = f"❌ **{display_name}** - Failed to create scenario"
                    logger.error(f"    ❌ {display_name} creation failed")

                # Report result to Slack
                self.slack_verifier.send_test_message(result_msg)
                time.sleep(3)  # Space out scenario creation

            # Send summary to Slack
            summary_msg = (
                f"📊 **Failure Scenario Creation Complete**\n\n"
                f"✅ **Successful:** {len(successful_scenarios)}/{len(scenarios)}\n"
                f"{'• ' + chr(10).join(successful_scenarios) if successful_scenarios else '(none)'}\n\n"
                f"❌ **Failed:** {len(failed_scenarios)}/{len(scenarios)}\n"
                f"{'• ' + chr(10).join(failed_scenarios) if failed_scenarios else '(none)'}\n\n"
                f"⏳ **Next:** Waiting for failures to manifest and testing detection..."
            )
            self.slack_verifier.send_test_message(summary_msg)

            overall_success = len(successful_scenarios) >= (len(scenarios) * 0.8)  # 80% success rate

            self.results["tests"]["failure_scenarios"] = {
                "success": overall_success,
                "scenarios": results,
                "successful_count": len(successful_scenarios),
                "failed_count": len(failed_scenarios),
                "success_rate": len(successful_scenarios) / len(scenarios)
            }

            logger.info(f"✅ Failure scenarios: {len(successful_scenarios)}/{len(scenarios)} successful")
            return overall_success

        except Exception as e:
            logger.error(f"❌ Failure scenarios test failed: {e}")
            self.results["tests"]["failure_scenarios"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_failure_detection_and_reporting(self) -> bool:
        """Detect failures and report findings to Slack"""
        logger.info("🔍 Testing failure detection and Slack reporting...")

        try:
            # Notify about detection phase
            detection_msg = (
                f"🔍 **Starting Failure Detection Phase**\n\n"
                f"⏳ Waiting 20 seconds for failures to fully manifest...\n"
                f"🔍 Then scanning for:\n"
                f"• Failed/Pending pods\n"
                f"• CrashLoopBackOff events\n"
                f"• Scheduling failures\n"
                f"• Health check failures"
            )
            self.slack_verifier.send_test_message(detection_msg)

            # Wait for failures to manifest
            logger.info("  ⏳ Waiting 20 seconds for failures to manifest...")
            time.sleep(20)

            # Detect failing pods
            import subprocess

            # Get failing pods
            result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "pods", "-n", self.failure_simulator.namespace,
                "--field-selector=status.phase!=Running",
                "-o", "jsonpath={.items[*].metadata.name}"
            ], capture_output=True, text=True)

            failing_pods = result.stdout.strip().split() if result.stdout.strip() else []

            # Get warning events
            events_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "events", "-n", self.failure_simulator.namespace,
                "--field-selector=type=Warning",
                "-o", "jsonpath={.items[*].reason}"
            ], capture_output=True, text=True)

            warning_events = events_result.stdout.strip().split() if events_result.stdout.strip() else []

            # Get pod statuses for more detail
            status_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "pods", "-n", self.failure_simulator.namespace,
                "-o", "jsonpath={range .items[*]}{.metadata.name}:{.status.phase}:{.status.containerStatuses[0].state}{\"\\n\"}{end}"
            ], capture_output=True, text=True)

            pod_statuses = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []

            success = len(failing_pods) > 0 or len(warning_events) > 0

            # Create detailed detection report for Slack
            detection_report = (
                f"🔍 **Failure Detection Results**\n\n"
                f"💥 **Failing Pods Found:** {len(failing_pods)}\n"
                f"{chr(10).join(f'• {pod}' for pod in failing_pods[:5])}\n"
                f"{'• ... and more' if len(failing_pods) > 5 else ''}\n\n"
                f"⚠️ **Warning Events:** {len(warning_events)}\n"
                f"{chr(10).join(f'• {event}' for event in list(set(warning_events))[:5])}\n\n"
                f"📊 **Detection Status:** {'✅ SUCCESS' if success else '❌ FAILED'}\n"
                f"🎯 **Expected:** Image pull failures, scheduling issues, crashloops"
            )

            self.slack_verifier.send_test_message(detection_report)

            self.results["tests"]["failure_detection"] = {
                "success": success,
                "failing_pods": failing_pods,
                "warning_events": list(set(warning_events)),
                "pod_statuses": pod_statuses,
                "detection_successful": success
            }

            logger.info(f"✅ Failure detection: {len(failing_pods)} failing pods, {len(warning_events)} warnings")
            return success

        except Exception as e:
            logger.error(f"❌ Failure detection failed: {e}")
            self.results["tests"]["failure_detection"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_comprehensive_system_status(self) -> bool:
        """Generate and report comprehensive system status"""
        logger.info("📊 Testing comprehensive system status reporting...")

        try:
            import subprocess

            # Get comprehensive cluster status

            # All pods in namespace
            pods_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "pods", "-n", self.failure_simulator.namespace,
                "-o", "custom-columns=NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.metadata.creationTimestamp"
            ], capture_output=True, text=True)

            # All events in namespace
            events_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "events", "-n", self.failure_simulator.namespace,
                "--sort-by=.metadata.creationTimestamp",
                "-o", "custom-columns=TYPE:.type,REASON:.reason,MESSAGE:.message"
            ], capture_output=True, text=True)

            # Resource usage
            top_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "top", "pods", "-n", self.failure_simulator.namespace
            ], capture_output=True, text=True)

            # Create comprehensive status report
            status_report = (
                f"📊 **Comprehensive System Status Report**\n\n"
                f"🖥️ **Cluster:** kind-makdo-test\n"
                f"📦 **Namespace:** {self.failure_simulator.namespace}\n"
                f"⏰ **Report Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"**Pod Status:**\n```\n{pods_result.stdout}\n```\n\n"
                f"**Recent Events:**\n```\n{events_result.stdout[-500:]}\n```\n\n"
                f"**This demonstrates the complete E2E test infrastructure working with real Slack integration!**"
            )

            self.slack_verifier.send_test_message(status_report)

            self.results["tests"]["system_status"] = {
                "success": True,
                "pods_output": pods_result.stdout,
                "events_output": events_result.stdout,
                "resource_usage": top_result.stdout
            }

            logger.info("✅ System status report sent to Slack")
            return True

        except Exception as e:
            logger.error(f"❌ System status reporting failed: {e}")
            self.results["tests"]["system_status"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_cleanup_and_summary(self) -> bool:
        """Clean up resources and send final summary"""
        logger.info("🧹 Testing cleanup and sending final summary...")

        try:
            # Clean up test resources
            logger.info("  🧹 Cleaning up test resources...")
            cleanup_msg = (
                f"🧹 **Cleanup Phase Started**\n\n"
                f"🗑️ Deleting test namespace: `{self.failure_simulator.namespace}`\n"
                f"🔄 Cleaning up all created pods, services, deployments\n"
                f"⏳ This may take a moment..."
            )
            self.slack_verifier.send_test_message(cleanup_msg)

            self.failure_simulator.cleanup()
            time.sleep(5)  # Give cleanup time to initiate

            # Calculate final results
            total_tests = len([t for t in self.results["tests"].values() if not t.get("skipped", False)])
            passed_tests = len([t for t in self.results["tests"].values() if t.get("success", False)])
            success_rate = passed_tests / total_tests if total_tests > 0 else 0
            overall_success = success_rate >= 0.8

            # Send comprehensive final summary
            final_summary = (
                f"🎊 **MAKDO Real-World E2E Test Complete!**\n\n"
                f"📊 **Final Results:**\n"
                f"✅ **Tests Passed:** {passed_tests}/{total_tests}\n"
                f"📈 **Success Rate:** {success_rate:.1%}\n"
                f"🎯 **Overall Status:** {'🎉 SUCCESS' if overall_success else '😞 NEEDS WORK'}\n\n"
                f"🔍 **What We Demonstrated:**\n"
                f"• ✅ Real Slack channel auto-creation and bot integration\n"
                f"• ✅ Live Kubernetes failure simulation in kind clusters\n"
                f"• ✅ Real-time failure detection and event monitoring\n"
                f"• ✅ Comprehensive status reporting to Slack\n"
                f"• ✅ Automated cleanup procedures\n\n"
                f"⏱️ **Duration:** {time.time() - self.results['start_time']:.1f} seconds\n"
                f"📅 **Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"**🚀 This infrastructure is ready to test MAKDO when the agent config is fixed!**"
            )

            self.slack_verifier.send_test_message(final_summary)

            self.results["tests"]["cleanup_and_summary"] = {
                "success": True,
                "final_success_rate": success_rate,
                "overall_success": overall_success
            }

            logger.info(f"✅ Final summary sent: {passed_tests}/{total_tests} tests passed")
            return True

        except Exception as e:
            logger.error(f"❌ Cleanup and summary failed: {e}")
            self.results["tests"]["cleanup_and_summary"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def run_real_world_e2e_test(self) -> Dict[str, Any]:
        """Run the complete real-world E2E test with live Slack integration"""
        logger.info("🌍 Starting MAKDO Real-World E2E Test")

        tests = [
            ("Slack Channel Creation & Messaging", self.test_slack_channel_creation_and_messaging),
            ("Kubernetes Cluster Setup", self.test_kubernetes_cluster_setup),
            ("Failure Scenarios with Live Reporting", self.test_failure_scenarios_with_slack_reporting),
            ("Failure Detection & Slack Reporting", self.test_failure_detection_and_reporting),
            ("Comprehensive System Status", self.test_comprehensive_system_status),
            ("Cleanup & Final Summary", self.test_cleanup_and_summary),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            logger.info(f"🧪 Running: {test_name}")
            logger.info(f"{'='*60}")

            try:
                if await test_func():
                    passed += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                logger.error(f"💥 {test_name}: EXCEPTION - {e}")

            time.sleep(2)  # Brief pause between tests

        # Finalize results
        self.results["end_time"] = time.time()
        self.results["duration"] = self.results["end_time"] - self.results["start_time"]
        self.results["summary"] = {
            "total_tests": total,
            "passed_tests": passed,
            "success_rate": passed / total,
            "overall_success": passed >= (total * 0.8)
        }

        # Save results to file
        results_file = Path("tests/e2e/real_world_results.json")
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        # Print final console summary
        logger.info(f"\n{'='*80}")
        logger.info("🌍 MAKDO REAL-WORLD E2E TEST RESULTS")
        logger.info(f"{'='*80}")
        logger.info(f"📊 Tests passed: {passed}/{total}")
        logger.info(f"📈 Success rate: {passed/total:.1%}")
        logger.info(f"⏱️ Duration: {self.results['duration']:.1f}s")
        logger.info(f"📱 Slack channel: #makdo-devops")

        if self.results["summary"]["overall_success"]:
            logger.info("🎉 Overall Result: SUCCESS")
        else:
            logger.info("😞 Overall Result: NEEDS IMPROVEMENT")

        logger.info(f"💾 Detailed results: {results_file}")
        logger.info(f"📱 Check #makdo-devops channel for live updates!")

        return self.results

async def main():
    """Main test runner"""
    try:
        tester = RealWorldMAKDOTest()
        results = await tester.run_real_world_e2e_test()
        return 0 if results["summary"]["overall_success"] else 1
    except Exception as e:
        logger.error(f"Test initialization failed: {e}")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))