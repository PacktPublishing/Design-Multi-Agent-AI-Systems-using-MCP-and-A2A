"""A2A Manager - Singleton for managing A2A infrastructure."""

import atexit
import logging
import threading
from typing import Optional, Dict

from .a2a_client import A2AClient, A2AServerConfig
from .a2a_message_pump import A2AMessagePump
from .a2a_executor import A2AExecutor

logger = logging.getLogger(__name__)


class A2AManager:
    """Singleton manager for A2A infrastructure.
    
    This class manages the lifecycle of A2A clients and message pump.
    It provides a centralized point for initialization and cleanup.
    """
    
    # Singleton state (class-level)
    _message_pump: Optional[A2AMessagePump] = None
    _executor: Optional[A2AExecutor] = None
    _a2a_clients: Dict[str, A2AClient] = {}  # Map of server_name -> A2AClient
    _cleanup_registered = False
    _lock = threading.Lock()
    _initialized = False
    
    @classmethod
    def initialize(cls, memory_dir: str, session_id: str, message_injector=None):
        """Initialize A2A infrastructure.
        
        Args:
            memory_dir: Directory for A2A state persistence
            session_id: Session ID for A2A integration
            message_injector: Optional callback for injecting system messages
        """
        with cls._lock:
            if cls._initialized:
                logger.debug("A2AManager already initialized")
                return
            
            # Create message pump
            cls._message_pump = A2AMessagePump(memory_dir, session_id)

            # Create executor
            cls._executor = A2AExecutor(cls._message_pump)

            # Set message injector if provided
            if message_injector:
                cls._message_pump.set_message_injector(message_injector)
            
            # Register cleanup on first initialization
            if not cls._cleanup_registered:
                atexit.register(cls.cleanup)
                cls._cleanup_registered = True
            
            cls._initialized = True
            logger.debug("A2AManager initialized")
    
    @classmethod
    def ensure_client(cls, server_config: A2AServerConfig) -> A2AClient:
        """Ensure an A2A client exists for a specific server, creating if needed.

        Args:
            server_config: Configuration for the A2A server

        Returns:
            A2AClient instance for the server
        """
        with cls._lock:
            if server_config.name not in cls._a2a_clients:
                client = A2AClient()
                # Store the server config in the client for later use
                client._server_configs[server_config.name] = server_config
                cls._a2a_clients[server_config.name] = client
                
                # Update message pump with new client if initialized
                if cls._message_pump:
                    cls._message_pump.set_a2a_clients(cls._a2a_clients)
            
            return cls._a2a_clients[server_config.name]
    
    @classmethod
    def get_message_pump(cls) -> Optional[A2AMessagePump]:
        """Get the message pump instance.

        Returns:
            A2AMessagePump instance or None if not initialized
        """
        return cls._message_pump

    @classmethod
    def get_executor(cls) -> Optional[A2AExecutor]:
        """Get the A2A executor instance.

        Returns:
            A2AExecutor instance or None if not initialized
        """
        return cls._executor
    
    @classmethod
    def configure_message_pump(cls):
        """Configure the message pump with all registered clients."""
        if cls._message_pump and cls._a2a_clients:
            cls._message_pump.set_a2a_clients(cls._a2a_clients)
            logger.debug(f"Message pump configured with {len(cls._a2a_clients)} clients")
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Check if A2AManager is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return cls._initialized
    
    @classmethod
    def cleanup(cls):
        """Cleanup all A2A resources. Called automatically on exit."""
        import asyncio
        
        with cls._lock:
            if not cls._initialized:
                return
            
            logger.debug("A2AManager cleanup starting")
            
            try:
                # Create event loop for cleanup if needed
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    close_loop = True
                else:
                    close_loop = False
                
                # Cleanup executor
                cls._executor = None

                # Cleanup message pump
                if cls._message_pump is not None:
                    try:
                        loop.run_until_complete(cls._message_pump.shutdown())
                    except Exception as e:
                        logger.debug(f"Error shutting down A2A message pump: {e}")
                    cls._message_pump = None
                
                # Cleanup all A2A clients
                for server_name, client in cls._a2a_clients.items():
                    try:
                        loop.run_until_complete(client.cleanup())
                        logger.debug(f"Cleaned up A2A client for {server_name}")
                    except Exception as e:
                        logger.debug(f"Error cleaning up A2A client {server_name}: {e}")
                cls._a2a_clients.clear()
                
                # Close loop if we created it
                if close_loop and not loop.is_closed():
                    loop.close()
                
                cls._initialized = False
                logger.debug("A2AManager cleanup completed")
                
            except Exception as e:
                logger.error(f"Error during A2AManager cleanup: {e}")
    
    @classmethod
    def reset(cls):
        """Reset the manager state. Useful for testing."""
        with cls._lock:
            cls.cleanup()
            cls._message_pump = None
            cls._executor = None
            cls._a2a_clients = {}
            cls._initialized = False
            cls._cleanup_registered = False