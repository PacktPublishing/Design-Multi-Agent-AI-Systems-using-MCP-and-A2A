import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Optional, Mapping, Any
from backend.object_model import LLMProvider
import yaml
import toml

@dataclass
class ToolConfig:
    """Configuration for tool discovery and management."""
    
    # Custom tools configuration
    tools_dir: Optional[str] = None
    tool_config: Mapping[str, dict] = field(default_factory=lambda: MappingProxyType({}))
    
    # Local MCP tools configuration  
    mcp_tools_dir: Optional[str] = None
    
    # Remote MCP servers configuration
    remote_mcp_servers: list = field(default_factory=list)
    
    
    @classmethod
    def from_engine_config(cls, engine_config):
        """Create ToolConfig from engine configuration."""
        return cls(
            tools_dir=getattr(engine_config, 'tools_dir', None),
            tool_config=getattr(engine_config, 'tool_config', {}),
            mcp_tools_dir=getattr(engine_config, 'mcp_tools_dir', None),
            remote_mcp_servers=getattr(engine_config, 'remote_mcp_servers', [])
        )


@dataclass
class Config:
    default_model_id: str
    tools_dir: str
    mcp_tools_dir: str
    memory_dir: str
    session_id: Optional[str] = None
    checkpoint_interval: int = 3
    summary_threshold_ratio: float = 0.8
    tool_config: Mapping[str, dict] = field(default_factory=lambda: MappingProxyType({}))
    provider_config: Mapping[str, dict] = field(default_factory=lambda: MappingProxyType({}))
    remote_mcp_servers: list = field(default_factory=list)

    def invariant(self):
        # Validate required directories
        assert self.default_model_id, "default_model_id must be set"
        assert os.path.isdir(self.tools_dir), f"Tools directory not found: {self.tools_dir}"
        assert os.path.isdir(self.mcp_tools_dir), f"MCP tools directory not found: {self.mcp_tools_dir}"
        assert os.path.isdir(self.memory_dir), f"Memory directory not found: {self.memory_dir}"

    @staticmethod
    def _interpolate_env_vars(value: Any) -> Any:
        """Recursively interpolate environment variables in a configuration value.
        
        Supports ${VAR} and $VAR syntax for environment variables.
        
        Parameters
        ----------
        value : Any
            The value to interpolate
            
        Returns
        -------
        Any
            The interpolated value
        """
        if isinstance(value, str):
            # Handle ${VAR} syntax
            if "${" in value and "}" in value:
                import re
                pattern = r'\${([a-zA-Z0-9_]+)}'
                matches = re.findall(pattern, value)
                
                for var_name in matches:
                    env_value = os.environ.get(var_name, '')
                    value = value.replace(f"${{{var_name}}}", env_value)
                    
            # Handle $VAR syntax
            elif value.startswith('$') and len(value) > 1:
                var_name = value[1:]
                value = os.environ.get(var_name, '')
                
            return value
        elif isinstance(value, dict):
            return {k: Config._interpolate_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [Config._interpolate_env_vars(item) for item in value]
        else:
            return value
            
    @staticmethod
    def from_file(filename: str) -> "Config":
        """Load configuration from a JSON, YAML, or TOML file.
        
        The file extension determines the format (.json, .yaml/.yml, or .toml).
        Required fields in the config file are: tools_dir, memory_dir, and default_model_id.
        Environment variables in the config are interpolated, supporting both ${VAR} and $VAR syntax.
        """
        path = Path(filename)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filename}")
            
        file_ext = path.suffix.lower()
        config_data: dict[str, Any] = {}
        
        # Load file content based on extension
        with open(filename, 'r') as f:
            if file_ext == '.json':
                config_data = json.load(f)
            elif file_ext in ('.yaml', '.yml'):
                config_data = yaml.safe_load(f)
            elif file_ext == '.toml':
                config_data = toml.load(f)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}. "
                                "Supported formats are: .json, .yaml, .yml, .toml")
                                
        # Interpolate environment variables in the loaded configuration
        config_data = Config._interpolate_env_vars(config_data)

        # Extract relevant configuration fields
        tools_dir = config_data.get('tools_dir')
        mcp_tools_dir = config_data.get('mcp_tools_dir')
        memory_dir = config_data.get('memory_dir')
        default_model_id = config_data.get('default_model_id')
        session_id = config_data.get('session_id')
        checkpoint_interval = config_data.get('checkpoint_interval', 3)
        summary_threshold_ratio = config_data.get('summary_threshold_ratio', 0.8)
        tool_config = config_data.get('tool_config', {})
        provider_config = config_data.get('provider_config', {})
        remote_mcp_servers = config_data.get('remote_mcp_servers', [])

        # Validate required fields
        if not tools_dir or not mcp_tools_dir or not memory_dir or not default_model_id:
            raise ValueError("Configuration file must contain 'tools_dir', 'mcp_tools_dir', 'memory_dir', "
                           "and 'default_model_id' fields")
            
        # For now, return a Config without llm_providers, which should be initialized
        # by the Engine class after loading providers using the provider_config
        conf = Config(
            default_model_id=default_model_id,
            tools_dir=tools_dir,
            mcp_tools_dir=mcp_tools_dir,
            memory_dir=memory_dir,
            session_id=session_id,
            checkpoint_interval=checkpoint_interval,
            summary_threshold_ratio=summary_threshold_ratio,
            tool_config=MappingProxyType(tool_config),
            provider_config=MappingProxyType(provider_config),
            remote_mcp_servers=remote_mcp_servers
        )

        conf.invariant()
        return conf
