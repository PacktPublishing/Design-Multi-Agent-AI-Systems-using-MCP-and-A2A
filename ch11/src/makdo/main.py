"""MAKDO Main Entry Point

Orchestrates the multi-agent Kubernetes DevOps system.
"""

import logging
import os
import time
import yaml
from pathlib import Path
from typing import Dict, Any

from ai_six.agent.agent import Agent
from ai_six.agent.config import Config
from dotenv import load_dotenv


def load_config(config_path: str = "config/makdo.yaml") -> Dict[str, Any]:
    """Load MAKDO configuration from YAML file."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file) as f:
        return yaml.safe_load(f)


def load_agent_config(agent_name: str) -> Dict[str, Any]:
    """Load agent-specific configuration from YAML file."""
    config_path = Path(f"src/makdo/agents/{agent_name}.yaml")

    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")

    with open(config_path) as f:
        return yaml.safe_load(f)


def create_coordinator_config() -> Config:
    """Create coordinator agent config with sub-agents."""
    return Config.from_file("src/makdo/agents/coordinator.yaml")


def create_k8s_ai_session(cluster_context: str, api_url: str = "http://localhost:9998") -> str:
    """Create a k8s-ai session and return the session token."""
    import subprocess
    import requests

    logger = logging.getLogger("makdo")

    try:
        # Get kubeconfig for the cluster
        logger.info(f"Getting kubeconfig for context: {cluster_context}")
        kubeconfig = subprocess.check_output(
            ["kubectl", "config", "view", f"--context={cluster_context}", "--minify", "--raw"],
            text=True
        )

        # Create session via Admin API
        logger.info(f"Creating k8s-ai session for {cluster_context}...")
        response = requests.post(
            f"{api_url}/sessions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "cluster_name": cluster_context,
                "kubeconfig": kubeconfig,
                "ttl_hours": 24.0
            },
            timeout=30.0
        )

        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            logger.info(f"✅ Created session for {cluster_context}: {session_token[:20]}...")
            return session_token
        else:
            logger.error(f"Failed to create session: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error creating k8s-ai session: {e}")
        return None


def setup_tool_call_monitoring(coordinator: Agent):
    """Setup comprehensive tool call monitoring for all agents."""
    from functools import wraps
    import json

    logger = logging.getLogger("makdo.tools")

    def wrap_agent_tools(agent, agent_name):
        """Wrap all tools for an agent to add logging."""
        for tool_name, tool in list(agent.tool_dict.items()):
            original_run = tool.run

            @wraps(original_run)
            def logged_run(*args, _tool_name=tool_name, _agent_name=agent_name, _orig_run=original_run, **kwargs):
                # Log tool call
                logger.info(f"🔧 [{_agent_name}] Calling tool: {_tool_name}")
                logger.info(f"   Args: {args}")
                logger.info(f"   Kwargs: {kwargs}")

                # For A2A tools, log the message parameter specifically
                if 'message' in kwargs:
                    logger.info(f"   📨 A2A Message: {kwargs['message'][:200]}...")

                try:
                    result = _orig_run(*args, **kwargs)
                    logger.info(f"✅ [{_agent_name}] Tool {_tool_name} completed")
                    logger.info(f"   Result preview: {str(result)[:300]}...")
                    return result
                except Exception as e:
                    logger.error(f"❌ [{_agent_name}] Tool {_tool_name} failed: {e}")
                    raise

            tool.run = logged_run

    # Wrap coordinator tools
    wrap_agent_tools(coordinator, "Coordinator")

    # Wrap sub-agent tools (sub-agents are stored as AgentTool instances in tool_dict)
    for tool_name, tool in coordinator.tool_dict.items():
        if tool_name.startswith("agent_"):
            agent_name = tool_name.replace("agent_", "")
            if hasattr(tool, 'agent'):
                wrap_agent_tools(tool.agent, agent_name)
                logger.info(f"✅ Wrapped tools for {agent_name}")


def start_coordinator(coordinator: Agent, config: Dict[str, Any]):
    """Start the coordinator agent."""
    logging.info("Starting MAKDO Coordinator")

    # Get monitoring configuration
    monitoring_config = config.get("monitoring", {})

    # Allow environment variable override for testing
    check_interval = int(os.getenv("MAKDO_CHECK_INTERVAL",
                                    monitoring_config.get("check_interval", 60)))

    logger = logging.getLogger("makdo")

    # Get cluster and k8s-ai configuration
    clusters = config.get("clusters", [])
    k8s_ai_config = config.get("k8s_ai", {})

    if not clusters:
        logger.warning("No clusters configured - MAKDO will start but won't monitor anything")
        cluster_context = None
        session_token = None
    else:
        # Use the first configured cluster
        cluster_config = clusters[0]
        cluster_context = cluster_config.get("context")
        api_url = k8s_ai_config.get("base_url", "http://localhost:9998")

        logger.info(f"Target cluster: {cluster_context}")
        logger.info(f"k8s-ai API URL: {api_url}")

        # Create k8s-ai session
        session_token = create_k8s_ai_session(cluster_context, api_url)
        if not session_token:
            logger.warning("Failed to create k8s-ai session - continuing without it")
            session_token = None

    # Inject session token into sub-agent sessions via SystemMessage (following ai-six v0.14.3 pattern)
    from ai_six.object_model import SystemMessage

    # Sub-agents are stored as AgentTool instances in the coordinator's tool_dict
    # AgentTool instances have a .agent attribute that is the actual Agent
    injected_count = 0
    if session_token and cluster_context:
        for tool_name, tool in coordinator.tool_dict.items():
            # Check if this is an agent tool (starts with "agent_")
            if tool_name.startswith("agent_"):
                # Get the agent name from the tool name
                agent_name = tool_name.replace("agent_", "")

                # Only inject into Analyzer and Fixer agents
                if agent_name in ["MAKDO_Analyzer", "MAKDO_Fixer"]:
                    # Access the actual agent from the AgentTool wrapper
                    if hasattr(tool, 'agent'):
                        agent = tool.agent

                        # CRITICAL: Clear old session messages to prevent stale session IDs from being used
                        # Old session summaries contain wrong session tokens that confuse the agent
                        old_message_count = len(agent.session.messages)
                        agent.session.messages.clear()
                        logger.info(f"   Cleared {old_message_count} old messages from {agent_name}")

                        # Create SystemMessage with session token and format instructions
                        session_context = SystemMessage(
                            content=f"""K8s Cluster Session: You have been given access to the '{cluster_context}' Kubernetes cluster.

Session Token: {session_token}

When using the k8s diagnostic tools, format your message parameter as:
"kubernetes_resource_health: session_token={session_token}, resource_type=pod, namespace=all"

CRITICAL: Always use namespace=all to check ALL namespaces, not just default!

Example:
- To check all pods: message="kubernetes_resource_health: session_token={session_token}, resource_type=pod, namespace=all"
- To diagnose issue: message="kubernetes_diagnose_issue: session_token={session_token}, issue_description=check pods not starting, namespace=all"

Always include the session_token and use namespace=all in your message."""
                        )

                        # Inject into agent's session
                        agent.session.messages.append(session_context)
                        logger.info(f"✅ Injected session token SystemMessage into {agent_name}")
                        logger.info(f"   Session token: {session_token[:30]}...")
                        injected_count += 1

        if injected_count > 0:
            logger.info(f"✅ k8s-ai session token configured for {injected_count} sub-agent(s)")
        else:
            logger.warning("Could not find any sub-agents to inject session token")
    else:
        logger.info("Skipping session token injection (no k8s-ai session available)")

    logger.info(f"Starting health check loop (interval: {check_interval}s)")

    try:
        while True:
            try:
                # Request a health check from the coordinator
                logger.info("="*80)
                logger.info("🔍 Initiating cluster health check...")
                logger.info("="*80)

                prompt = (
                    "Perform a comprehensive health check across all registered clusters. "
                    "Use the Analyzer agent to identify any issues, then use the Slack Bot agent "
                    "to report findings to the #makdo-devops channel. "
                    "If critical issues are found, use the Fixer agent to attempt remediation."
                )

                logger.info(f"📤 Coordinator prompt: {prompt}")
                response = coordinator.send_message(prompt)
                logger.info("="*80)
                logger.info(f"✅ Health check completed")
                logger.info(f"📨 Coordinator response: {response[:500]}...")
                logger.info("="*80)

                # Clear session history to prevent context overflow and message ordering issues
                # Keep only system message - each health check cycle is independent
                if len(coordinator.session.messages) > 3:
                    logger.info(f"Clearing old session messages ({len(coordinator.session.messages)} messages)")
                    # Keep only system message (first message)
                    system_message = coordinator.session.messages[0] if coordinator.session.messages else None
                    coordinator.session.messages.clear()
                    if system_message:
                        coordinator.session.messages.append(system_message)
                    logger.info(f"Session reset to {len(coordinator.session.messages)} message (system message only)")

            except Exception as e:
                logger.error(f"Error during health check cycle: {e}")
                import traceback
                traceback.print_exc()

            # Wait before next check
            time.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("MAKDO Coordinator shutting down...")
    finally:
        # Save session on exit
        coordinator.session.save()


def setup_logging(config: Dict[str, Any]):
    """Configure logging based on system configuration."""
    log_config = config.get("logging", {})

    # Use DEBUG level if MAKDO_DEBUG env var is set, otherwise use config
    if os.getenv("MAKDO_DEBUG"):
        level = logging.DEBUG
    else:
        level = getattr(logging, log_config.get("level", "INFO").upper())

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if log_config.get("format") == "json":
        # In production, you might use structured logging
        pass

    logging.basicConfig(level=level, format=format_str)

    # Create log directory if specified
    log_file = log_config.get("file")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Enable verbose logging for ai_six and A2A components during debug
    if os.getenv("MAKDO_DEBUG"):
        logging.getLogger("ai_six").setLevel(logging.INFO)
        logging.getLogger("makdo.tools").setLevel(logging.INFO)


def main():
    """Main entry point for MAKDO system."""
    # Load environment variables
    load_dotenv()

    # Load system configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please copy config/makdo.example.yaml to config/makdo.yaml and configure")
        return 1

    # Setup logging
    setup_logging(config)

    logger = logging.getLogger("makdo")
    logger.info("Starting MAKDO - Multi-Agent Kubernetes DevOps System")

    try:
        # Create coordinator with sub-agents
        coordinator_config = create_coordinator_config()
        coordinator = Agent(coordinator_config)

        logger.info("Coordinator and sub-agents created successfully")

        # Setup comprehensive tool call monitoring
        logger.info("Setting up tool call monitoring...")
        setup_tool_call_monitoring(coordinator)
        logger.info("✅ Tool call monitoring enabled for all agents")

        # Start the coordinator (main orchestrator)
        start_coordinator(coordinator, config)

    except Exception as e:
        logger.error(f"Failed to start MAKDO: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())