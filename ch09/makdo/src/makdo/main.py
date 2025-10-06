"""MAKDO Main Entry Point

Orchestrates the multi-agent Kubernetes DevOps system.
"""

import asyncio
import logging
import os
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


async def start_coordinator(agent: Agent):
    """Start the coordinator agent."""
    logging.info("Starting MAKDO Coordinator")

    # AI-6 handles everything - just run the agent
    await agent.run()


def setup_logging(config: Dict[str, Any]):
    """Configure logging based on system configuration."""
    log_config = config.get("logging", {})

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


async def main():
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

        # Start the coordinator (main orchestrator)
        await start_coordinator(coordinator)

    except Exception as e:
        logger.error(f"Failed to start MAKDO: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))