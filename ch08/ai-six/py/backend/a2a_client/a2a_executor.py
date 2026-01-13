"""A2A Executor - Handles sync-to-async bridging for A2A operations."""

import asyncio
from typing import Optional

from .a2a_message_pump import A2AMessagePump


def _is_event_loop_running() -> bool:
    """Check if there's a running event loop in the current thread."""
    try:
        asyncio.current_task()
        return True
    except RuntimeError:
        return False


class A2AExecutor:
    """Handles sync-to-async bridging for A2A operations.

    This class encapsulates the complexity of executing async A2A operations
    from synchronous contexts, handling both scenarios where an event loop
    is already running and where one needs to be created.
    """

    def __init__(self, message_pump: A2AMessagePump):
        """Initialize the executor with a message pump.

        Args:
            message_pump: The A2A message pump for handling async operations
        """
        self.message_pump = message_pump

    def execute_skill(self, server_name: str, skill_name: str,
                     message: str, task_id: Optional[str] = None) -> str:
        """Execute A2A skill with automatic sync/async handling.

        Args:
            server_name: Name of the A2A server
            skill_name: Name of the skill to execute
            message: Message to send to the skill
            task_id: Optional task ID for sending message to existing task

        Returns:
            Response string from the A2A operation
        """
        if not self.message_pump:
            return "Error: A2A not initialized. Please configure A2A integration."

        def _execute_task():
            """Execute the appropriate A2A task based on parameters."""
            if task_id:
                return self.message_pump.send_message_to_task(task_id, message)
            else:
                msg_to_send = message if message else f"Execute {skill_name} skill"
                return self.message_pump.start_task(server_name, skill_name, msg_to_send)

        try:
            if _is_event_loop_running():
                # We're in an async context, use run_coroutine_threadsafe to run in message pump's background loop
                future = asyncio.run_coroutine_threadsafe(
                    _execute_task(),
                    self.message_pump.event_loop  # Use public property instead of private field
                )
                return future.result(timeout=30)
            else:
                # No running event loop, create new one and run directly
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(_execute_task())
                finally:
                    loop.close()

        except Exception as e:
            return f"A2A skill execution failed: {e}"