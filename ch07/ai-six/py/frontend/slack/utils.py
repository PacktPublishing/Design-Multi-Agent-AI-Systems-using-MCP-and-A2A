"""
Slack-specific utilities for AI-6.

This module provides helpers specifically for the Slack frontend,
including channel-specific engine creation and management.
"""

import os
from pathlib import Path
from typing import Optional

from backend.engine.config import Config
from backend.engine.engine import Engine
from frontend.common.engine_utils import create_from_config


def create_channel_engine(
    base_config_path: str,
    channel_id: str,
    base_memory_dir: Optional[str] = None,
    env_file_path: Optional[str] = None
) -> Engine:
    """Create an Engine instance for a specific Slack channel.
    
    Args:
        base_config_path: Path to the base configuration file
        channel_id: Slack channel identifier to create a separate configuration
        base_memory_dir: Optional override for the base memory directory
        env_file_path: Optional path to a .env file to load environment variables from
        
    Returns:
        An Engine instance configured for the specific channel
    """
    # If env_file_path is provided, check that it exists
    if env_file_path and not os.path.exists(env_file_path):
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        possible_env_path = script_dir / env_file_path
        if os.path.exists(possible_env_path):
            env_file_path = str(possible_env_path)
        else:
            print(f"Warning: Environment file {env_file_path} not found")
    
    # Load the base configuration
    config = Config.from_file(base_config_path)
    
    # Determine memory directory
    memory_base = Path(base_memory_dir or config.memory_dir)
    channel_memory_dir = memory_base / channel_id
    channel_memory_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a channel-specific config file
    file_ext = Path(base_config_path).suffix
    channel_config_path = str(channel_memory_dir / f"config{file_ext}")
    
    # Load the base config data and modify for the channel
    with open(base_config_path, 'r') as f:
        config_content = f.read()
    
    config_content = config_content.replace(
        config.memory_dir, 
        str(channel_memory_dir)
    )
    
    # Write the modified config for this channel
    with open(channel_config_path, 'w') as f:
        f.write(config_content)
    
    # Create the engine using our helper which loads environment variables
    engine, _ = create_from_config(
        config_path=channel_config_path,
        env_file_path=env_file_path
    )
    
    return engine
