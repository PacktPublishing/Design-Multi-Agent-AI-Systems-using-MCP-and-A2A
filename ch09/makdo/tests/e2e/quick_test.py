#!/usr/bin/env python3
"""
Quick MAKDO E2E Test - Minimal version for fast iteration
Tests core functionality without full cluster setup
"""

import asyncio
import json
import logging
import subprocess
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MAKDO-QuickTest")

class QuickMAKDOTest:
    """Lightweight E2E test for rapid iteration"""

    def __init__(self):
        self.test_namespace = "makdo-quick-test"
        self.results = {
            "test_type": "quick",
            "start_time": time.time(),
            "tests": {}
        }

    async def test_agent_creation(self) -> bool:
        """Test that MAKDO agents can be created"""
        logger.info("Testing agent creation...")

        try:
            # Test minimal agent creation (like test_minimal.py)
            result = subprocess.run([
                "uv", "run", "python", "test_minimal.py"
            ], capture_output=True, text=True, timeout=30)

            success = result.returncode == 0 and "Agent created successfully" in result.stdout
            self.results["tests"]["agent_creation"] = {
                "success": success,
                "output": result.stdout,
                "error": result.stderr if not success else None
            }

            if success:
                logger.info("✅ Agent creation test passed")
            else:
                logger.error(f"❌ Agent creation failed: {result.stderr}")

            return success

        except Exception as e:
            logger.error(f"Agent creation test error: {e}")
            self.results["tests"]["agent_creation"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_config_loading(self) -> bool:
        """Test configuration loading"""
        logger.info("Testing configuration loading...")

        try:
            # Import and test config loading
            from src.makdo.main import load_config

            config = load_config("config/makdo.yaml")

            # Verify essential config sections
            required_sections = ["clusters", "k8s_ai", "agents", "operations"]
            missing_sections = [s for s in required_sections if s not in config]

            success = len(missing_sections) == 0

            self.results["tests"]["config_loading"] = {
                "success": success,
                "config_sections": list(config.keys()),
                "missing_sections": missing_sections
            }

            if success:
                logger.info("✅ Configuration loading test passed")
            else:
                logger.error(f"❌ Missing config sections: {missing_sections}")

            return success

        except Exception as e:
            logger.error(f"Config loading test error: {e}")
            self.results["tests"]["config_loading"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_k8s_connectivity(self) -> bool:
        """Test Kubernetes cluster connectivity"""
        logger.info("Testing Kubernetes connectivity...")

        try:
            # Test kubectl connectivity to both clusters
            clusters = ["kind-k8s-ai", "kind-makdo-test"]
            cluster_results = {}

            for cluster in clusters:
                try:
                    result = subprocess.run([
                        "kubectl", "--context", cluster, "cluster-info"
                    ], capture_output=True, text=True, timeout=10)

                    cluster_results[cluster] = result.returncode == 0

                except subprocess.TimeoutExpired:
                    cluster_results[cluster] = False
                except Exception:
                    cluster_results[cluster] = False

            success = any(cluster_results.values())  # At least one cluster working

            self.results["tests"]["k8s_connectivity"] = {
                "success": success,
                "clusters": cluster_results
            }

            if success:
                logger.info(f"✅ Kubernetes connectivity test passed: {cluster_results}")
            else:
                logger.error(f"❌ No clusters accessible: {cluster_results}")

            return success

        except Exception as e:
            logger.error(f"Kubernetes connectivity test error: {e}")
            self.results["tests"]["k8s_connectivity"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_k8s_ai_server(self) -> bool:
        """Test k8s-ai server connectivity"""
        logger.info("Testing k8s-ai server connectivity...")

        try:
            # Check if server is running
            response = requests.get("http://localhost:9999/health", timeout=5)
            server_running = response.status_code == 200

            if not server_running:
                logger.info("k8s-ai server not running, attempting to start...")
                # Try to start server (non-blocking)
                if os.path.exists("/Users/gigi/git/k8s-ai"):
                    subprocess.Popen([
                        "uv", "run", "k8s-ai-server",
                        "--context", "kind-k8s-ai",
                        "--port", "9999"
                    ], cwd="/Users/gigi/git/k8s-ai")

                    # Wait a bit and check again
                    time.sleep(5)
                    try:
                        response = requests.get("http://localhost:9999/health", timeout=3)
                        server_running = response.status_code == 200
                    except:
                        server_running = False

            self.results["tests"]["k8s_ai_server"] = {
                "success": server_running,
                "status_code": response.status_code if server_running else None
            }

            if server_running:
                logger.info("✅ k8s-ai server connectivity test passed")
            else:
                logger.warning("⚠️ k8s-ai server not accessible (this is okay for basic tests)")

            return True  # Not failing the test if server is not available

        except Exception as e:
            logger.warning(f"k8s-ai server test warning: {e}")
            self.results["tests"]["k8s_ai_server"] = {
                "success": False,
                "error": str(e)
            }
            return True  # Not a critical failure

    async def test_slack_mcp_server(self) -> bool:
        """Test Slack MCP server binary"""
        logger.info("Testing Slack MCP server binary...")

        try:
            # Check if binary exists and is executable
            slack_mcp_path = Path("bin/slack-mcp-server")
            binary_exists = slack_mcp_path.exists() and slack_mcp_path.is_file()

            if binary_exists:
                # Try to run with --help to verify it works
                result = subprocess.run([
                    str(slack_mcp_path), "--help"
                ], capture_output=True, text=True, timeout=5)

                binary_works = result.returncode == 0
            else:
                binary_works = False

            self.results["tests"]["slack_mcp_server"] = {
                "success": binary_exists and binary_works,
                "binary_exists": binary_exists,
                "binary_executable": binary_works if binary_exists else False
            }

            if binary_exists and binary_works:
                logger.info("✅ Slack MCP server binary test passed")
            else:
                logger.error(f"❌ Slack MCP server binary issue: exists={binary_exists}, works={binary_works}")

            return binary_exists and binary_works

        except Exception as e:
            logger.error(f"Slack MCP server test error: {e}")
            self.results["tests"]["slack_mcp_server"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def test_simple_failure_detection(self) -> bool:
        """Create a simple failing pod and see if it can be detected"""
        logger.info("Testing simple failure detection...")

        try:
            # Use any available cluster
            cluster = "kind-makdo-test"  # Default to test cluster

            # Create a simple failing pod
            pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: quick-test-failing-pod
  namespace: default
spec:
  containers:
  - name: failing-app
    image: nonexistent-image:latest
    imagePullPolicy: Always
  restartPolicy: Never
"""

            # Apply the pod
            with open("/tmp/quick-test-pod.yaml", "w") as f:
                f.write(pod_yaml)

            result = subprocess.run([
                "kubectl", "--context", cluster,
                "apply", "-f", "/tmp/quick-test-pod.yaml"
            ], capture_output=True, text=True)

            pod_created = result.returncode == 0

            if pod_created:
                # Wait a bit for failure to manifest
                time.sleep(10)

                # Check pod status
                status_result = subprocess.run([
                    "kubectl", "--context", cluster,
                    "get", "pod", "quick-test-failing-pod",
                    "-o", "jsonpath={.status.phase}"
                ], capture_output=True, text=True)

                pod_status = status_result.stdout.strip()
                failure_detected = pod_status in ["Failed", "Pending"]

                # Clean up
                subprocess.run([
                    "kubectl", "--context", cluster,
                    "delete", "pod", "quick-test-failing-pod",
                    "--ignore-not-found=true"
                ], capture_output=True)

                os.unlink("/tmp/quick-test-pod.yaml")

            else:
                failure_detected = False
                pod_status = "NotCreated"

            self.results["tests"]["simple_failure_detection"] = {
                "success": pod_created and failure_detected,
                "pod_created": pod_created,
                "pod_status": pod_status,
                "failure_detected": failure_detected
            }

            if pod_created and failure_detected:
                logger.info(f"✅ Simple failure detection test passed (status: {pod_status})")
            else:
                logger.error(f"❌ Simple failure detection failed: created={pod_created}, status={pod_status}")

            return pod_created and failure_detected

        except Exception as e:
            logger.error(f"Simple failure detection test error: {e}")
            self.results["tests"]["simple_failure_detection"] = {
                "success": False,
                "error": str(e)
            }
            return False

    async def run_quick_tests(self) -> Dict[str, Any]:
        """Run all quick tests"""
        logger.info("🚀 Starting MAKDO Quick E2E Tests")

        tests = [
            ("Agent Creation", self.test_agent_creation),
            ("Configuration Loading", self.test_config_loading),
            ("Kubernetes Connectivity", self.test_k8s_connectivity),
            ("k8s-ai Server", self.test_k8s_ai_server),
            ("Slack MCP Server", self.test_slack_mcp_server),
            ("Simple Failure Detection", self.test_simple_failure_detection),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            logger.info(f"\n--- Running: {test_name} ---")
            try:
                if await test_func():
                    passed += 1
            except Exception as e:
                logger.error(f"Test {test_name} threw exception: {e}")

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
        results_file = Path("tests/e2e/quick_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)

        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)

        # Print summary
        logger.info(f"\n{'='*50}")
        logger.info("MAKDO Quick Test Results")
        logger.info(f"{'='*50}")
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
    tester = QuickMAKDOTest()
    results = await tester.run_quick_tests()

    return 0 if results["summary"]["overall_success"] else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))