#!/usr/bin/env python3
"""
Comprehensive E2E Test for Async A2A Integration

This single test validates the complete async-to-sync A2A bridge functionality:
1. Immediate response pattern (no blocking)
2. Background task processing with SystemMessage injection
3. Multitasking capabilities
4. Task lifecycle management
5. Proper error handling with no ignored failures
"""

import sys
import os
import time
import subprocess
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.agent.agent import Agent
from backend.agent.config import Config
from backend.object_model import SystemMessage

# Load environment variables from .env file FIRST
from dotenv import load_dotenv
load_dotenv()

# Configure logging to catch errors only
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class A2AComprehensiveE2ETest:
    """Comprehensive E2E test for async A2A functionality."""

    def __init__(self):
        self.agent: Optional[Agent] = None
        self.server_process: Optional[subprocess.Popen] = None
        self.ollama_process: Optional[subprocess.Popen] = None
        self.test_start_time = datetime.now()
        self.errors: list[str] = []
        self.task_ids: list[str] = []

    def log_error(self, error: str):
        """Log an error and add to errors list - no ignored errors!"""
        logger.error(error)
        self.errors.append(f"[{datetime.now().strftime('%H:%M:%S')}] {error}")

    def assert_no_errors(self, context: str = ""):
        """Assert that no errors have occurred."""
        if self.errors:
            error_summary = f"\n=== ERRORS DETECTED{' IN ' + context if context else ''} ===\n"
            for error in self.errors:
                error_summary += f"  {error}\n"
            error_summary += f"=== END ERRORS ===\n"
            raise AssertionError(f"Test failed due to errors: {error_summary}")

    def check_service(self, name: str, url: str, expected_response: str = None) -> bool:
        """Check if a service is running."""
        response = requests.get(url, timeout=5)
        if expected_response and expected_response not in response.text:
            return False
        return response.status_code == 200

    def start_ollama(self) -> bool:
        """Start ollama service if not running."""
        print("🔧 Checking Ollama service...")

        # Check if ollama is already running
        if self.check_service("Ollama", "http://localhost:11434/api/tags"):
            print("✅ Ollama already running")
            return True

        print("🚀 Starting Ollama service...")
        try:
            # Start ollama serve
            self.ollama_process = subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=os.environ.copy()
            )

            # Wait for ollama to start
            for i in range(30):  # 30 second timeout
                if self.check_service("Ollama", "http://localhost:11434/api/tags"):
                    print("✅ Ollama started successfully")
                    return True
                time.sleep(1)
                print(f"   Waiting for Ollama... ({i+1}/30)")

            # Check if process died
            if self.ollama_process.poll() is not None:
                stderr = self.ollama_process.stderr.read().decode() if self.ollama_process.stderr else "No stderr"
                self.log_error(f"Ollama process died: {stderr}")
                return False

            self.log_error("Ollama service failed to start within 30 seconds")
            return False

        except FileNotFoundError:
            self.log_error("Ollama command not found - please install ollama")
            return False
        except Exception as e:
            self.log_error(f"Failed to start Ollama: {e}")
            return False

    def start_k8s_ai_server(self) -> bool:
        """Start k8s-ai A2A server if not running."""
        print("🔧 Checking k8s-ai A2A server...")

        # Check if server is already running
        if self.check_service("k8s-ai", "http://localhost:9999/.well-known/agent.json"):
            print("✅ k8s-ai server already running")
            return True

        print("🚀 Starting k8s-ai A2A server...")
        k8s_ai_path = Path.home() / "git" / "k8s-ai"
        if not k8s_ai_path.exists():
            self.log_error(f"k8s-ai not found at {k8s_ai_path}")
            return False

        try:
            # Start server in background
            cmd = ['python', '-m', 'k8s_ai.server.main', '--context', 'kind-k8s-ai',
                   '--host', '127.0.0.1', '--port', '9999']
            self.server_process = subprocess.Popen(
                cmd,
                cwd=k8s_ai_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            # Wait for server to start
            for i in range(20):  # 20 second timeout
                if self.check_service("k8s-ai", "http://localhost:9999/.well-known/agent.json"):
                    print("✅ k8s-ai server started successfully")
                    return True

                # Check if process died
                if self.server_process.poll() is not None:
                    output = self.server_process.stdout.read() if self.server_process.stdout else "No output"
                    self.log_error(f"k8s-ai server process died: {output}")
                    return False

                time.sleep(1)
                print(f"   Waiting for k8s-ai server... ({i+1}/20)")

            self.log_error("k8s-ai server failed to start within 20 seconds")
            return False

        except Exception as e:
            self.log_error(f"Failed to start k8s-ai server: {e}")
            return False

    def setup_agent(self) -> bool:
        """Set up AI-6 agent with async A2A configuration."""
        print("🤖 Setting up AI-6 Agent with async A2A...")

        try:
            config_file = os.path.join(os.path.dirname(__file__), 'config_async.yaml')
            if not os.path.exists(config_file):
                self.log_error(f"Config file not found: {config_file}")
                return False

            config = Config.from_file(config_file)

            # Validate config has A2A servers
            if not config.a2a_servers:
                self.log_error("No A2A servers configured in config")
                return False

            # Create agent
            self.agent = Agent(config)

            # Check available tools
            a2a_tools = [name for name in self.agent.tool_dict.keys() if name.startswith('kind-k8s-ai_')]
            task_tools = [name for name in self.agent.tool_dict.keys() if name.startswith('a2a_')]

            if not a2a_tools:
                self.log_error("No A2A operation tools discovered")
                return False

            if len(task_tools) != 4:
                self.log_error(f"Expected 4 task management tools, found {len(task_tools)}: {task_tools}")
                return False

            print(f"✅ Agent ready with {len(a2a_tools)} A2A tools and {len(task_tools)} task tools")
            return True

        except Exception as e:
            self.log_error(f"Failed to setup agent: {e}")
            return False

    def test_immediate_response_pattern(self) -> bool:
        """Test that A2A tools return immediately without blocking."""
        print("\n🚀 Testing Immediate Response Pattern...")

        try:
            # Get first A2A tool
            a2a_tools = [name for name in self.agent.tool_dict.keys() if name.startswith('kind-k8s-ai_')]
            if not a2a_tools:
                self.log_error("No A2A tools available for testing")
                return False

            tool_name = a2a_tools[0]
            tool = self.agent.tool_dict[tool_name]

            # Record start time
            start_time = time.time()

            # Execute tool - should return immediately
            result = tool.run(message="List all pods in the cluster with their status")

            # Check response time (should be immediate, < 2 seconds)
            response_time = time.time() - start_time
            if response_time > 2.0:
                self.log_error(f"Tool took {response_time:.2f}s to respond - not immediate!")
                return False

            # Validate response format
            if "Started" not in result or "Monitoring" not in result:
                self.log_error(f"Unexpected immediate response format: {result}")
                return False

            # Extract task ID
            if "ID:" not in result:
                self.log_error(f"No task ID in response: {result}")
                return False

            task_id = result.split("ID:")[1].strip().split(")")[0]
            self.task_ids.append(task_id)

            print(f"✅ Immediate response in {response_time:.2f}s, task ID: {task_id}")
            return True

        except Exception as e:
            self.log_error(f"Immediate response test failed: {e}")
            return False

    def test_background_processing(self) -> bool:
        """Test background processing with SystemMessage injection."""
        print("\n📨 Testing Background Processing & SystemMessage Injection...")

        try:
            # Record initial message count
            initial_count = len(self.agent.session.messages)
            print(f"   Initial message count: {initial_count}")

            # Wait for background messages to arrive
            print("   Waiting for background SystemMessages...")
            max_wait = 15  # 15 seconds max wait
            messages_received = False

            for i in range(max_wait):
                time.sleep(1)
                current_count = len(self.agent.session.messages)

                if current_count > initial_count:
                    # Check if new messages are SystemMessages from A2A
                    new_messages = self.agent.session.messages[initial_count:]
                    system_messages = [msg for msg in new_messages if isinstance(msg, SystemMessage)]
                    a2a_messages = [msg for msg in system_messages if "A2A Task Update" in str(msg)]

                    if a2a_messages:
                        # Check if messages contain errors vs real responses
                        error_messages = [msg for msg in a2a_messages if "Task failed:" in str(msg) or "Error" in str(msg)]
                        success_messages = [msg for msg in a2a_messages if "Task failed:" not in str(msg) and "Error" not in str(msg)]

                        if error_messages and not success_messages:
                            self.log_error(f"All A2A messages are errors: {[str(msg)[:100] for msg in error_messages]}")
                            return False

                        print(f"✅ Received {len(a2a_messages)} A2A SystemMessages ({len(success_messages)} success, {len(error_messages)} errors)")
                        for msg in a2a_messages[:3]:  # Show first 3
                            content = str(msg)[:100]
                            print(f"     {content}...")

                        # Only consider it successful if we got real responses, not just errors
                        if success_messages:
                            messages_received = True
                            break
                        elif error_messages:
                            self.log_error("Only received error messages from A2A, no successful responses")
                            return False

                print(f"     Waiting... ({i+1}/{max_wait})")

            if not messages_received:
                self.log_error("No A2A SystemMessages received within timeout")
                return False

            return True

        except Exception as e:
            self.log_error(f"Background processing test failed: {e}")
            return False

    def test_multi_tasking(self) -> bool:
        """Test multitasking: start second task while first is running."""
        print("\n⚡ Testing Multi-tasking Capabilities...")

        try:
            # Get A2A tool
            a2a_tools = [name for name in self.agent.tool_dict.keys() if name.startswith('kind-k8s-ai_')]
            tool_name = a2a_tools[0]
            tool = self.agent.tool_dict[tool_name]

            # Start second task
            result = tool.run(message="Get detailed information about all services in the cluster")

            # Validate immediate response
            if "Started" not in result or "Monitoring" not in result:
                self.log_error(f"Second task unexpected response: {result}")
                return False

            # Extract second task ID
            task_id = result.split("ID:")[1].strip().split(")")[0]
            self.task_ids.append(task_id)

            # Verify both tasks are active
            list_result = self.agent.tool_dict['a2a_list_tasks'].run()

            if "Active A2A Tasks (2)" not in list_result:
                self.log_error(f"Expected 2 active tasks, got: {list_result}")
                return False

            # Verify both task IDs are in the list
            for task_id in self.task_ids:
                if task_id not in list_result:
                    self.log_error(f"Task {task_id} not found in active list")
                    return False

            print(f"✅ Multi-tasking working: 2 concurrent tasks active")
            return True

        except Exception as e:
            self.log_error(f"Multi-tasking test failed: {e}")
            return False

    def test_task_management(self) -> bool:
        """Test task management tools work correctly."""
        print("\n🛠️  Testing Task Management Tools...")

        try:
            if not self.task_ids:
                self.log_error("No task IDs available for management testing")
                return False

            task_id = self.task_ids[0]

            # Test task status
            status_result = self.agent.tool_dict['a2a_task_status'].run(task_id=task_id)
            if task_id not in status_result or "Status:" not in status_result:
                self.log_error(f"Invalid task status result: {status_result}")
                return False

            print("✅ Task status tool working")

            # Test send message to task
            message_result = self.agent.tool_dict['a2a_send_message'].run(
                task_id=task_id,
                message="Focus on pods that are not in 'Running' state"
            )

            if "Sent message" not in message_result:
                self.log_error(f"Send message failed: {message_result}")
                return False

            print("✅ Send message to task working")

            # Wait a bit for potential new messages
            time.sleep(2)

            return True

        except Exception as e:
            self.log_error(f"Task management test failed: {e}")
            return False

    def test_task_cancellation(self) -> bool:
        """Test task cancellation and cleanup."""
        print("\n🧹 Testing Task Cancellation & Cleanup...")

        try:
            # Cancel all active tasks
            cancelled_count = 0
            for task_id in self.task_ids:
                cancel_result = self.agent.tool_dict['a2a_cancel_task'].run(task_id=task_id)
                if "Cancelled" in cancel_result:
                    cancelled_count += 1
                    print(f"✅ Cancelled task: {task_id}")
                else:
                    # Task might have completed already - check if it's still active
                    list_result = self.agent.tool_dict['a2a_list_tasks'].run()
                    if task_id not in list_result:
                        print(f"✅ Task already completed: {task_id}")
                        cancelled_count += 1
                    else:
                        self.log_error(f"Failed to cancel task {task_id}: {cancel_result}")
                        return False

            # Verify no tasks are active
            time.sleep(1)  # Allow cleanup time
            list_result = self.agent.tool_dict['a2a_list_tasks'].run()
            if "No active A2A tasks" not in list_result:
                self.log_error(f"Tasks still active after cancellation: {list_result}")
                return False

            print(f"✅ Successfully cancelled/completed {cancelled_count} tasks")
            return True

        except Exception as e:
            self.log_error(f"Task cancellation test failed: {e}")
            return False

    def run_comprehensive_test(self) -> bool:
        """Run the complete comprehensive E2E test."""
        print("🧪 COMPREHENSIVE A2A E2E TEST")
        print("=" * 50)

        # Phase 1: Service Setup
        print("\n📋 Phase 1: Service Dependencies")
        if not self.start_ollama():
            return False
        self.assert_no_errors("Ollama startup")

        if not self.start_k8s_ai_server():
            return False
        self.assert_no_errors("k8s-ai server startup")

        if not self.setup_agent():
            return False
        self.assert_no_errors("Agent setup")

        # Phase 2: Core Async Functionality
        print("\n📋 Phase 2: Core Async A2A Functionality")
        if not self.test_immediate_response_pattern():
            return False
        self.assert_no_errors("Immediate response pattern")

        if not self.test_background_processing():
            return False
        self.assert_no_errors("Background processing")

        if not self.test_multi_tasking():
            return False
        self.assert_no_errors("Multi-tasking")

        # Phase 3: Task Management
        print("\n📋 Phase 3: Task Management")
        if not self.test_task_management():
            return False
        self.assert_no_errors("Task management")

        if not self.test_task_cancellation():
            return False
        self.assert_no_errors("Task cancellation")

        # Final validation - no errors throughout entire test
        self.assert_no_errors("Entire E2E test")

        # Success summary
        elapsed = datetime.now() - self.test_start_time
        print("\n" + "=" * 50)
        print("🎉 COMPREHENSIVE E2E TEST PASSED!")
        print("=" * 50)
        print(f"⏱️  Test duration: {elapsed.total_seconds():.1f} seconds")
        print(f"📊 Tasks processed: {len(self.task_ids)}")
        print(f"🔥 Async A2A Bridge: FULLY FUNCTIONAL")
        print("\n✅ Key Features Validated:")
        print("   • Immediate response pattern (no blocking)")
        print("   • Background task processing")
        print("   • SystemMessage injection for real-time updates")
        print("   • Multi-tasking (concurrent A2A operations)")
        print("   • Task lifecycle management")
        print("   • Proper error handling (no ignored errors)")

        return True

    def cleanup(self):
        """Clean up test resources."""
        print("\n🧹 Cleaning up test resources...")

        # Cancel any remaining tasks
        if self.agent:
            try:
                list_result = self.agent.tool_dict['a2a_list_tasks'].run()
                if "No active" not in list_result:
                    print("   Cancelling remaining tasks...")
                    for task_id in self.task_ids:
                        try:
                            self.agent.tool_dict['a2a_cancel_task'].run(task_id=task_id)
                        except:
                            pass
            except:
                pass

        # Stop k8s-ai server
        if self.server_process:
            print("   Stopping k8s-ai server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()

        # Note: Don't stop Ollama as it might be used by other processes
        # Just let the user know
        if self.ollama_process:
            print("   Note: Ollama server left running (may be used by other processes)")


def main():
    """Run the comprehensive E2E test."""
    test = A2AComprehensiveE2ETest()

    try:
        success = test.run_comprehensive_test()
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        test.log_error("Test interrupted by user")
        return 1

    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        test.log_error(f"Unexpected test failure: {e}")
        return 1

    finally:
        # Always clean up
        test.cleanup()

        # Show any errors that occurred
        if test.errors:
            print(f"\n❌ Test completed with {len(test.errors)} errors:")
            for error in test.errors:
                print(f"   {error}")


if __name__ == "__main__":
    sys.exit(main())
