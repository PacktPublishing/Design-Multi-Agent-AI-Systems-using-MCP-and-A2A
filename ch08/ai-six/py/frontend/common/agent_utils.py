"""
Common utilities for frontend Agent initialization and management.

This module provides helpers for creating and managing Agent instances
across different frontends (CLI, Chainlit, Slack, etc.).
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

from backend.agent.config import Config
from backend.agent.agent import Agent


def create_from_config(
    config_path: str, 
    session_id: Optional[str] = None,
    env_file_path: Optional[str] = None
) -> Tuple[Agent, Config]:
    """Create an Agent instance from a configuration file.
    
    Args:
        config_path: Path to the configuration file (JSON, YAML, or TOML)
        session_id: Optional session ID to load after initialization
        env_file_path: Optional path to a .env file to load environment variables from
        
    Returns:
        A tuple containing (agent, config) where agent is the initialized
        Agent instance and config is the loaded Config object.
    """
    # Load environment variables from .env file if provided
    if env_file_path and os.path.exists(env_file_path):
        load_dotenv(env_file_path)
    else:
        load_dotenv()

    # Load the configuration
    config = Config.from_file(config_path)
    
    # Create required directories if they don't exist
    memory_dir = Path(config.memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Create the agent from the configuration
    agent = Agent.from_config_file(config_path)
    
    # Load session if provided
    if session_id:
        if not agent.load_session(session_id):
            raise ValueError(f"Session ID not found: {session_id}")
    
    return agent, config
