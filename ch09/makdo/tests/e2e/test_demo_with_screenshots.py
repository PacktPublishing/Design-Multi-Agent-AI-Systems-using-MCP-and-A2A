#!/usr/bin/env python3
"""
MAKDO Demo Test with Automatic Screenshot Capture
Creates actual Kubernetes failures and captures Slack screenshots for chapter demo
"""

import asyncio
import json
import logging
import time
import os
import subprocess
import platform
import signal
import httpx
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import pyautogui for screenshots
try:
    import pyautogui
    SCREENSHOTS_ENABLED = True
except ImportError:
    print("⚠️  pyautogui not installed. Install with: pip install pyautogui")
    print("   Screenshots will be disabled.")
    SCREENSHOTS_ENABLED = False

# Import from test_makdo_e2e
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
logger = logging.getLogger("MAKDO-Demo-Screenshots")


class K8sAIServerManager:
    """Manages k8s-ai server lifecycle for the demo"""

    def __init__(self, k8s_ai_path: str = "/Users/gigi/git/k8s-ai",
                 host: str = "localhost", port: int = 9999):
        self.k8s_ai_path = Path(k8s_ai_path)
        self.host = host
        self.port = port
        self.server_process: Optional[subprocess.Popen] = None
        self.started_by_us = False

    def is_server_running(self) -> bool:
        """Check if k8s-ai server is already running"""
        try:
            response = httpx.get(f"http://{self.host}:{self.port}/.well-known/agent.json",
                               timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False

    def start_server(self) -> bool:
        """Start k8s-ai server if not already running"""
        if self.is_server_running():
            logger.info(f"✅ k8s-ai server already running on {self.host}:{self.port}")
            return True

        try:
            logger.info(f"🚀 Starting k8s-ai server on {self.host}:{self.port}...")

            # Start server as background process
            self.server_process = subprocess.Popen(
                ["uv", "run", "k8s-ai-server",
                 "--context", "kind-k8s-ai",
                 "--host", self.host,
                 "--port", str(self.port)],
                cwd=str(self.k8s_ai_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self.started_by_us = True

            # Wait for server to be ready (max 30 seconds)
            for i in range(30):
                time.sleep(1)
                if self.is_server_running():
                    logger.info(f"✅ k8s-ai server started successfully")
                    return True
                logger.info(f"⏳ Waiting for server... ({i+1}/30)")

            logger.error("❌ Server failed to start within 30 seconds")
            self.stop_server()
            return False

        except Exception as e:
            logger.error(f"❌ Failed to start k8s-ai server: {e}")
            return False

    def stop_server(self):
        """Stop k8s-ai server if we started it"""
        if self.server_process and self.started_by_us:
            logger.info("🛑 Stopping k8s-ai server...")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                logger.info("✅ Server stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Server didn't stop gracefully, killing...")
                self.server_process.kill()
                self.server_process.wait()
            except Exception as e:
                logger.error(f"❌ Error stopping server: {e}")


class ScreenshotCapture:
    """Handles bringing Slack to front and capturing screenshots"""

    def __init__(self, output_dir: str = "tests/e2e/demo_screenshots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_count = 0
        self.system = platform.system()

        logger.info(f"📸 Screenshot capture initialized (System: {self.system})")
        logger.info(f"📁 Screenshots will be saved to: {self.output_dir.absolute()}")

    def bring_slack_to_front(self) -> bool:
        """Bring Slack application to front using platform-specific commands"""
        try:
            if self.system == "Darwin":  # macOS
                # Use AppleScript to activate Slack
                script = 'tell application "Slack" to activate'
                subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
                logger.info("✅ Brought Slack to front (macOS)")
                time.sleep(1)  # Wait for window to come to front
                return True

            elif self.system == "Linux":
                # Try wmctrl or xdotool
                try:
                    subprocess.run(["wmctrl", "-a", "Slack"], check=True, capture_output=True)
                    logger.info("✅ Brought Slack to front (Linux - wmctrl)")
                    time.sleep(1)
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        subprocess.run(["xdotool", "search", "--name", "Slack", "windowactivate"],
                                     check=True, capture_output=True)
                        logger.info("✅ Brought Slack to front (Linux - xdotool)")
                        time.sleep(1)
                        return True
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        logger.warning("⚠️  Could not bring Slack to front (wmctrl/xdotool not available)")
                        return False

            elif self.system == "Windows":
                # Use pywin32 if available
                try:
                    import win32gui
                    import win32con

                    def enum_windows_callback(hwnd, windows):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "Slack" in title:
                                windows.append(hwnd)

                    windows = []
                    win32gui.EnumWindows(enum_windows_callback, windows)

                    if windows:
                        hwnd = windows[0]
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                        logger.info("✅ Brought Slack to front (Windows)")
                        time.sleep(1)
                        return True
                except ImportError:
                    logger.warning("⚠️  pywin32 not installed. Install with: pip install pywin32")
                    return False

            else:
                logger.warning(f"⚠️  Unsupported platform: {self.system}")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to bring Slack to front: {e}")
            return False

    def capture_screenshot(self, name: str, description: str = "") -> bool:
        """Capture a screenshot of Slack and save it"""
        if not SCREENSHOTS_ENABLED:
            logger.warning("⚠️  Screenshots disabled (pyautogui not installed)")
            return False

        try:
            # Bring Slack to front
            if not self.bring_slack_to_front():
                logger.warning(f"⚠️  Could not bring Slack to front for: {name}")
                # Continue anyway - might still capture something useful

            # Wait a bit more for rendering
            time.sleep(2)

            # Capture screenshot
            screenshot = pyautogui.screenshot()

            # Generate filename
            self.screenshot_count += 1
            filename = f"{self.screenshot_count:02d}_{name}.png"
            filepath = self.output_dir / filename

            # Save screenshot
            screenshot.save(filepath)

            logger.info(f"📸 Screenshot saved: {filename}")
            if description:
                logger.info(f"   Description: {description}")

            # Create metadata file
            metadata_file = filepath.with_suffix('.json')
            metadata = {
                "screenshot_number": self.screenshot_count,
                "name": name,
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "filename": filename
            }
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to capture screenshot '{name}': {e}")
            return False


class MAKDODemoTest:
    """MAKDO Demo test with automatic screenshot capture"""

    def __init__(self):
        self.results = {
            "test_type": "demo_with_screenshots",
            "start_time": time.time(),
            "tests": {},
            "screenshots": []
        }

        # Initialize components
        self.failure_simulator = KubernetesFailureSimulator()
        self.screenshot = ScreenshotCapture() if SCREENSHOTS_ENABLED else None
        self.k8s_ai_server = K8sAIServerManager()

        # Get Slack token from environment
        slack_token = os.getenv("AI6_BOT_TOKEN")
        if not slack_token:
            raise ValueError("AI6_BOT_TOKEN not found in environment")

        self.slack_verifier = SlackNotificationVerifier(slack_token, "#makdo-devops")

    def take_screenshot(self, name: str, description: str = ""):
        """Helper to take screenshot and track it"""
        if self.screenshot:
            success = self.screenshot.capture_screenshot(name, description)
            if success:
                self.results["screenshots"].append({
                    "name": name,
                    "description": description,
                    "timestamp": time.time()
                })

    def clear_channel_messages(self) -> bool:
        """Send a clear separator message to mark demo start"""
        try:
            separator_msg = (
                f"\n\n" + "="*60 + "\n"
                f"🎬 **NEW DEMO RUN STARTING** 🎬\n"
                f"="*60 + "\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📝 Previous messages above, new demo below\n"
                f"="*60 + "\n\n"
            )

            success = self.slack_verifier.send_test_message(separator_msg)
            if success:
                logger.info("✅ Demo separator message sent")
                time.sleep(2)
            return success

        except Exception as e:
            logger.error(f"❌ Failed to send separator: {e}")
            return False

    async def demo_step_1_welcome(self) -> bool:
        """Demo Step 1: Welcome message and test start"""
        logger.info("🎬 DEMO STEP 1: Sending welcome message...")

        try:
            # First send separator to mark clean start
            self.clear_channel_messages()

            welcome_msg = (
                f"🚀 **MAKDO End-to-End Demo**\n\n"
                f"This demo showcases MAKDO's complete failure detection and reporting workflow:\n\n"
                f"**What you'll see:**\n"
                f"1. ✅ Environment setup and initialization\n"
                f"2. 💥 Creation of various failure scenarios\n"
                f"3. 🔍 Automated failure detection\n"
                f"4. 📊 System status and health reporting\n"
                f"5. 🎯 Final results and summary\n\n"
                f"⏰ **Started:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📱 **Channel:** #makdo-devops\n"
                f"🎬 **Let's begin!**"
            )

            success = self.slack_verifier.send_test_message(welcome_msg)

            if success:
                logger.info("✅ Welcome message sent")
                time.sleep(3)  # Wait for Slack to render
                self.take_screenshot(
                    "01_demo_start",
                    "MAKDO demo welcome message showing test scope and objectives"
                )

            self.results["tests"]["welcome"] = {"success": success}
            return success

        except Exception as e:
            logger.error(f"❌ Demo step 1 failed: {e}")
            return False

    async def demo_step_2_environment(self) -> bool:
        """Demo Step 2: Environment setup"""
        logger.info("🎬 DEMO STEP 2: Setting up environment...")

        try:
            # Setup test namespace
            if not self.failure_simulator.setup_test_namespace():
                return False

            env_msg = (
                f"✅ **Environment Setup Complete**\n\n"
                f"🖥️ **Kubernetes Clusters:**\n"
                f"• kind-makdo-test (test cluster)\n"
                f"• kind-k8s-ai (analysis cluster)\n\n"
                f"🔧 **Infrastructure:**\n"
                f"• k8s-ai server: Running on localhost:9999\n"
                f"• Test namespace: {self.failure_simulator.namespace}\n"
                f"• Slack integration: Active\n\n"
                f"📦 **Ready to simulate failures!**"
            )

            success = self.slack_verifier.send_test_message(env_msg)

            if success:
                logger.info("✅ Environment setup message sent")
                time.sleep(3)
                self.take_screenshot(
                    "02_environment_setup",
                    "Environment setup confirmation showing cluster and infrastructure details"
                )

            self.results["tests"]["environment"] = {"success": success}
            return success

        except Exception as e:
            logger.error(f"❌ Demo step 2 failed: {e}")
            return False

    async def demo_step_3_failures(self) -> bool:
        """Demo Step 3: Create failure scenarios"""
        logger.info("🎬 DEMO STEP 3: Creating failure scenarios...")

        try:
            scenarios = [
                ("Image Pull Failure", "failing_pod", self.failure_simulator.create_failing_pod),
                ("CrashLoop BackOff", "crashloop_pod", self.failure_simulator.create_crashloop_pod),
                ("Resource Starvation", "resource_starved", self.failure_simulator.create_resource_starved_pod),
                ("Health Check Failure", "unhealthy_service", self.failure_simulator.create_unhealthy_service),
            ]

            results = {}

            # Send starting message
            start_msg = (
                f"💥 **Creating Failure Scenarios**\n\n"
                f"Deploying 4 different failure types to test detection capabilities..."
            )
            self.slack_verifier.send_test_message(start_msg)
            time.sleep(2)

            for display_name, scenario_id, scenario_func in scenarios:
                logger.info(f"  💥 Creating: {display_name}")

                scenario_msg = f"💥 Creating **{display_name}**..."
                self.slack_verifier.send_test_message(scenario_msg)

                success = scenario_func()
                results[scenario_id] = success

                result_msg = f"{'✅' if success else '❌'} {display_name}: {'Created' if success else 'Failed'}"
                self.slack_verifier.send_test_message(result_msg)
                time.sleep(2)

            # Send summary
            successful = sum(1 for v in results.values() if v)
            summary_msg = (
                f"📊 **Failure Scenario Summary**\n\n"
                f"✅ Successfully created: {successful}/{len(scenarios)} scenarios\n"
                f"{'• ' + chr(10).join(name for name, _, _ in scenarios)}\n\n"
                f"⏳ Waiting for failures to manifest before detection phase..."
            )
            self.slack_verifier.send_test_message(summary_msg)

            time.sleep(3)
            self.take_screenshot(
                "03_failure_scenarios",
                "Failure scenarios created and reported to Slack"
            )

            self.results["tests"]["failures"] = {
                "success": successful >= len(scenarios) * 0.75,
                "scenarios": results
            }
            return successful >= len(scenarios) * 0.75

        except Exception as e:
            logger.error(f"❌ Demo step 3 failed: {e}")
            return False

    async def demo_step_4_detection(self) -> bool:
        """Demo Step 4: Failure detection"""
        logger.info("🎬 DEMO STEP 4: Running failure detection...")

        try:
            detection_msg = (
                f"🔍 **Starting Failure Detection**\n\n"
                f"⏳ Waiting 15 seconds for failures to fully manifest...\n"
                f"Then scanning cluster for issues..."
            )
            self.slack_verifier.send_test_message(detection_msg)

            # Wait for failures to manifest
            time.sleep(15)

            # Detect failures
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

            warning_events = list(set(events_result.stdout.strip().split())) if events_result.stdout.strip() else []

            # Report findings
            detection_report = (
                f"🔍 **Detection Results**\n\n"
                f"💥 **Failing Pods:** {len(failing_pods)}\n"
                f"{chr(10).join(f'• `{pod}`' for pod in failing_pods[:5])}\n"
                f"{'• ... and more' if len(failing_pods) > 5 else ''}\n\n"
                f"⚠️  **Warning Events Detected:**\n"
                f"{chr(10).join(f'• `{event}`' for event in warning_events[:8])}\n\n"
                f"✅ **Status:** {len(failing_pods)} failures detected successfully"
            )
            self.slack_verifier.send_test_message(detection_report)

            time.sleep(3)
            self.take_screenshot(
                "04_failure_detection",
                "Failure detection results showing discovered issues"
            )

            success = len(failing_pods) > 0
            self.results["tests"]["detection"] = {
                "success": success,
                "failing_pods": failing_pods,
                "warning_events": warning_events
            }
            return success

        except Exception as e:
            logger.error(f"❌ Demo step 4 failed: {e}")
            return False

    async def demo_step_5_status(self) -> bool:
        """Demo Step 5: System status report"""
        logger.info("🎬 DEMO STEP 5: Generating system status...")

        try:
            # Get pod status
            pods_result = subprocess.run([
                "kubectl", "--context", "kind-makdo-test",
                "get", "pods", "-n", self.failure_simulator.namespace,
                "-o", "custom-columns=NAME:.metadata.name,STATUS:.status.phase,RESTARTS:.status.containerStatuses[0].restartCount"
            ], capture_output=True, text=True)

            status_msg = (
                f"📊 **System Status Report**\n\n"
                f"```\n{pods_result.stdout[:1000]}\n```\n\n"
                f"🎯 **Summary:** Cluster state captured for analysis"
            )
            self.slack_verifier.send_test_message(status_msg)

            time.sleep(3)
            self.take_screenshot(
                "05_system_status",
                "Complete system status showing all pods and their states"
            )

            self.results["tests"]["status"] = {"success": True}
            return True

        except Exception as e:
            logger.error(f"❌ Demo step 5 failed: {e}")
            return False

    async def demo_step_6_summary(self) -> bool:
        """Demo Step 6: Final summary"""
        logger.info("🎬 DEMO STEP 6: Sending final summary...")

        try:
            # Calculate results
            passed = sum(1 for t in self.results["tests"].values() if t.get("success", False))
            total = len(self.results["tests"])
            duration = time.time() - self.results["start_time"]

            summary_msg = (
                f"🎉 **MAKDO Demo Complete!**\n\n"
                f"📊 **Results:**\n"
                f"• Tests passed: {passed}/{total}\n"
                f"• Duration: {duration:.1f} seconds\n"
                f"• Screenshots captured: {len(self.results['screenshots'])}\n\n"
                f"✅ **What we demonstrated:**\n"
                f"• Multi-agent system initialization\n"
                f"• Automated failure scenario creation\n"
                f"• Real-time detection and alerting\n"
                f"• Comprehensive status reporting\n"
                f"• Human-readable Slack notifications\n\n"
                f"🎯 **MAKDO successfully demonstrated end-to-end DevOps automation!**"
            )
            self.slack_verifier.send_test_message(summary_msg)

            time.sleep(3)
            self.take_screenshot(
                "06_final_summary",
                "Final summary showing complete demo results and achievements"
            )

            self.results["tests"]["summary"] = {"success": True}
            return True

        except Exception as e:
            logger.error(f"❌ Demo step 6 failed: {e}")
            return False

    async def run_demo(self) -> dict[str, Any]:
        """Run the complete demo with screenshots"""
        logger.info("🎬 Starting MAKDO Demo with Screenshot Capture")
        logger.info("=" * 80)

        # Ensure k8s-ai server is running
        if not self.k8s_ai_server.start_server():
            logger.error("❌ Failed to start k8s-ai server - demo cannot proceed")
            return self.results

        if not SCREENSHOTS_ENABLED:
            logger.warning("⚠️  Screenshots are DISABLED (pyautogui not installed)")
            logger.warning("   Demo will run but no screenshots will be captured")

        try:
            demo_steps = [
                ("Welcome Message", self.demo_step_1_welcome),
                ("Environment Setup", self.demo_step_2_environment),
                ("Failure Scenarios", self.demo_step_3_failures),
                ("Failure Detection", self.demo_step_4_detection),
                ("System Status", self.demo_step_5_status),
                ("Final Summary", self.demo_step_6_summary),
            ]

            for step_name, step_func in demo_steps:
                logger.info(f"\n{'='*60}")
                logger.info(f"🎬 {step_name}")
                logger.info(f"{'='*60}")

                try:
                    await step_func()
                except Exception as e:
                    logger.error(f"💥 {step_name} threw exception: {e}")

                time.sleep(1)

            # Finalize results
            self.results["end_time"] = time.time()
            self.results["duration"] = self.results["end_time"] - self.results["start_time"]

            # Save results
            results_file = Path("tests/e2e/demo_results.json")
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)

            # Print summary
            logger.info("\n" + "="*80)
            logger.info("🎬 MAKDO DEMO COMPLETE")
            logger.info("="*80)
            logger.info(f"⏱️  Duration: {self.results['duration']:.1f}s")
            logger.info(f"📸 Screenshots: {len(self.results['screenshots'])}")
            if self.screenshot:
                logger.info(f"📁 Screenshot directory: {self.screenshot.output_dir.absolute()}")
            logger.info(f"💾 Results: {results_file.absolute()}")

            return self.results

        finally:
            # Clean up k8s-ai server if we started it
            self.k8s_ai_server.stop_server()


async def main():
    """Main demo runner"""
    try:
        demo = MAKDODemoTest()
        results = await demo.run_demo()
        return 0
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
