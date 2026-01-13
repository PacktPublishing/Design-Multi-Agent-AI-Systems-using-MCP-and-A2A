"""A2A Message Pump for async-to-sync communication bridge."""

import asyncio
import concurrent.futures
import json
import time
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
import logging

from backend.object_model import SystemMessage
from backend.a2a_client.a2a_client import A2AClient, A2AServerConfig


logger = logging.getLogger(__name__)


@dataclass
class A2ATaskInfo:
    """Information about an active A2A task."""
    task_id: str
    server_name: str
    skill_id: str
    status: str
    created_at: datetime
    last_checked: datetime
    last_message_at: Optional[datetime] = None
    user_input_required: bool = False
    user_input_prompt: Optional[str] = None
    artifacts: list[str] = None
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
    
    @classmethod
    def from_dict(cls, data: dict) -> 'A2ATaskInfo':
        """Create TaskInfo from dictionary (for persistence)."""
        # Convert ISO datetime strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_checked'] = datetime.fromisoformat(data['last_checked'])
        if data.get('last_message_at'):
            data['last_message_at'] = datetime.fromisoformat(data['last_message_at'])
        return cls(**data)
    
    def to_dict(self) -> dict:
        """Convert TaskInfo to dictionary (for persistence)."""
        data = asdict(self)
        # Convert datetime objects to ISO strings for JSON serialization
        data['created_at'] = self.created_at.isoformat()
        data['last_checked'] = self.last_checked.isoformat()
        if self.last_message_at:
            data['last_message_at'] = self.last_message_at.isoformat()
        return data


class A2AMessagePump:
    """Message pump for handling async A2A communication in sync AI-6 context."""
    
    def __init__(self, memory_dir: str, session_id: str):
        self.memory_dir = memory_dir
        self.session_id = session_id
        # Map of server_name -> A2AClient instance
        self.a2a_clients: Dict[str, 'A2AClient'] = {}
        
        # Active tasks tracking
        self.active_tasks: Dict[str, A2ATaskInfo] = {}
        self.task_monitors: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.poll_interval = 5.0  # seconds
        self.max_task_age = timedelta(hours=24)  # Auto-cleanup old tasks
        
        # Callback for message injection
        self.message_injector: Optional[Callable[[SystemMessage], None]] = None
        
        # State persistence
        self.state_dir = Path(memory_dir) / "a2a_state"
        self.state_dir.mkdir(exist_ok=True)
        self.state_file = self.state_dir / f"active_tasks_{session_id}.json"
        
        # Background event loop for async tasks
        self._loop = None
        self._loop_thread = None
        self._loop_started = threading.Event()
        
        # Load persisted state
        self._load_state()
        
        # Start background event loop
        self._start_event_loop()
    
    def _start_event_loop(self):
        """Start the background event loop in a separate thread."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_started.set()
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()
        self._loop_started.wait()  # Wait for loop to start
    
    def set_message_injector(self, injector: Callable[[SystemMessage], None]):
        """Set the callback function for injecting SystemMessages."""
        self.message_injector = injector
    
    def set_a2a_clients(self, clients: Dict[str, 'A2AClient']):
        """Set the A2A clients map."""
        self.a2a_clients = clients

    @property
    def event_loop(self) -> 'asyncio.AbstractEventLoop':
        """Get the background event loop for this message pump."""
        return self._loop
    
    async def start_task(self, server_name: str, skill_id: str, message: str) -> str:
        """Start a new A2A task and begin monitoring.
        
        Returns:
            Immediate response message for the user
        """
        if server_name not in self.a2a_clients:
            return f"Error: No A2A client configured for server {server_name}"
        
        try:
            # Generate task ID immediately
            task_id = f"{server_name}_{skill_id}_{int(time.time())}"
            
            # Create task info
            now = datetime.now()
            task_info = A2ATaskInfo(
                task_id=task_id,
                server_name=server_name,
                skill_id=skill_id,
                status="starting",
                created_at=now,
                last_checked=now
            )
            
            # Add to active tasks immediately
            self.active_tasks[task_id] = task_info
            
            # Start the actual A2A task and monitoring in background
            # This includes agent discovery if needed
            # Use the background event loop
            future = asyncio.run_coroutine_threadsafe(
                self._start_and_monitor_task(task_id, server_name, message),
                self._loop
            )
            # Store the future for tracking
            self.task_monitors[task_id] = future
            
            # Persist state
            self._save_state()
            
            # Return immediate response
            return f"Started {skill_id} task on {server_name} (ID: {task_id}). Monitoring for updates..."
            
        except Exception as e:
            logger.error(f"Failed to start A2A task: {e}")
            return f"Failed to start A2A task: {e}"
    
    async def send_message_to_task(self, task_id: str, message: str) -> str:
        """Send a message to an active A2A task.
        
        Since A2A is stateless, this creates a new message stream.
        We'll stream the response and inject it as interim messages.
        
        Returns:
            Immediate response confirming message sent
        """
        if task_id not in self.active_tasks:
            return f"Task {task_id} not found or no longer active"
        
        task_info = self.active_tasks[task_id]
        
        # Start streaming the response in background
        asyncio.run_coroutine_threadsafe(
            self._stream_message_response(task_id, task_info.server_name, message),
            self._loop
        )
        
        return f"Sent message to task {task_id}: {message}"
    
    async def _stream_message_response(self, task_id: str, server_name: str, message: str):
        """Stream response from sending a message to A2A server."""
        try:
            task_info = self.active_tasks.get(task_id)
            if not task_info:
                return
            
            # Mark task as active again
            task_info.status = "running"
            task_info.last_checked = datetime.now()
            
            # Stream the response
            message_count = 0
            buffer = []
            
            async for response_chunk in self.a2a_clients[server_name].send_message(server_name, message):
                if response_chunk:
                    message_count += 1
                    task_info.last_message_at = datetime.now()
                    buffer.append(response_chunk)
                    
                    # Inject updates periodically
                    if '\n' in response_chunk or len(buffer) >= 5:
                        combined = ''.join(buffer)
                        if combined.strip():
                            await self._inject_interim_message(
                                task_id, 
                                f"[A2A Response] {combined}"
                            )
                        buffer = []
                        await asyncio.sleep(0.1)
            
            # Inject any remaining content
            if buffer:
                combined = ''.join(buffer)
                if combined.strip():
                    await self._inject_interim_message(
                        task_id, 
                        f"[A2A Response] {combined}"
                    )
            
            # Update state
            await self._inject_interim_message(
                task_id, 
                f"Response complete. Received {message_count} chunks."
            )
            self._save_state()
            
        except Exception as e:
            logger.error(f"Failed to stream message response for task {task_id}: {e}")
            await self._inject_interim_message(
                task_id, 
                f"Error streaming response: {e}"
            )
    
    async def _start_and_monitor_task(self, task_id: str, server_name: str, message: str):
        """Start the actual A2A task and begin monitoring."""
        
        try:
            task_info = self.active_tasks.get(task_id)
            if not task_info:
                logger.error(f"Task {task_id} not found in active tasks")
                return
            
            # Ensure agent is discovered first (in background)
            client = self.a2a_clients.get(server_name)
            if not client:
                logger.error(f"No A2A client for server {server_name}")
                task_info.status = "failed"
                await self._inject_interim_message(
                    task_id, 
                    f"No A2A client configured for server {server_name}"
                )
                return
            
            try:
                if server_name not in client._agent_cards:
                    # Check if we have a stored config for this server
                    if server_name in client._server_configs:
                        server_config = client._server_configs[server_name]
                        await client._discover_agent(server_config)
                    else:
                        # Fallback for unknown servers (shouldn't happen in normal flow)
                        server_config = A2AServerConfig(
                            name=server_name,
                            url="http://localhost:9999"  # TODO: Make this configurable
                        )
                        await client._discover_agent(server_config)
            except Exception as e:
                logger.error(f"Agent discovery failed for {server_name}: {e}")
                task_info.status = "failed"
                await self._inject_interim_message(
                    task_id, 
                    f"Agent discovery failed: {e}"
                )
                return
            
            # Start the A2A task and stream responses
            response_generator = None
            try:
                # Update status to running
                task_info.status = "running"
                self._save_state()
                
                # Stream responses and inject each as an interim message
                message_count = 0
                buffer = []
                
                response_generator = client.send_message(server_name, message)
                async for response_chunk in response_generator:
                    if response_chunk:
                        message_count += 1
                        task_info.last_message_at = datetime.now()
                        buffer.append(response_chunk)
                        
                        # Inject updates periodically or when we get a complete line
                        if '\n' in response_chunk or len(buffer) >= 5:
                            combined = ''.join(buffer)
                            if combined.strip():
                                await self._inject_interim_message(
                                    task_id, 
                                    f"[A2A Update] {combined}"
                                )
                            buffer = []
                            
                            # Small delay to avoid overwhelming the session
                            await asyncio.sleep(0.1)
                
                # Inject any remaining buffered content
                if buffer:
                    combined = ''.join(buffer)
                    if combined.strip():
                        await self._inject_interim_message(
                            task_id, 
                            f"[A2A Update] {combined}"
                        )
                
                logger.info(f"Task {task_id} stream complete. Total messages: {message_count}")
                
                # Mark task as completed
                task_info.status = "completed"
                if message_count > 0:
                    await self._inject_interim_message(
                        task_id, 
                        f"Task completed. Received {message_count} response chunks."
                    )
                else:
                    logger.warning(f"Task {task_id} completed with no response chunks")
                self._save_state()
                
            except asyncio.CancelledError:
                logger.info(f"Task {task_id} was cancelled")
                task_info.status = "cancelled"
                # Properly close the generator if it exists
                if response_generator:
                    await response_generator.aclose()
                raise
            except Exception as e:
                logger.error(f"Error in A2A task {task_id}: {e}")
                task_info.status = "failed"
                await self._inject_interim_message(
                    task_id, 
                    f"Task failed: {e}"
                )
                # Properly close the generator if it exists
                if response_generator:
                    await response_generator.aclose()
                return
            finally:
                # Ensure generator is closed
                if response_generator:
                    try:
                        await response_generator.aclose()
                    except Exception:
                        pass
            
            # Now continue with regular monitoring
            await self._monitor_task(task_id)
            
        except Exception as e:
            logger.error(f"Unexpected error in start_and_monitor for task {task_id}: {e}")
    
    async def _monitor_task(self, task_id: str):
        """Background monitoring of an A2A task.
        
        Since A2A streaming happens in _start_and_monitor_task,
        this just keeps the task alive until completion or cancellation.
        """
        
        try:
            while task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                
                # Check if task is completed
                if task_info.status in ["completed", "failed"]:
                    logger.info(f"Task {task_id} finished with status: {task_info.status}")
                    break
                
                # Update last checked time
                task_info.last_checked = datetime.now()
                
                # Wait before next check
                await asyncio.sleep(self.poll_interval)
                
        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for task {task_id}")
        except Exception as e:
            logger.error(f"Unexpected error monitoring task {task_id}: {e}")
        finally:
            # Clean up the task from active tasks after a delay
            await asyncio.sleep(5)  # Keep task info for a bit after completion
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
                self._save_state()
            if task_id in self.task_monitors:
                del self.task_monitors[task_id]
    
    
    async def _inject_interim_message(self, task_id: str, content: str):
        """Inject an interim A2A message as SystemMessage."""
        if not self.message_injector:
            logger.warning("No message injector set - cannot deliver interim message")
            return
        
        # Format as user-friendly system message
        system_content = f"A2A Task Update [{task_id}]: {content}"
        system_message = SystemMessage(content=system_content)
        
        # Update task state
        if task_id in self.active_tasks:
            self.active_tasks[task_id].last_message_at = datetime.now()
        
        # Inject into conversation
        try:
            self.message_injector(system_message)
            logger.info(f"Injected interim message for task {task_id}: {content}")
        except Exception as e:
            logger.error(f"Failed to inject message for task {task_id}: {e}")
    
    def cancel_task(self, task_id: str) -> str:
        """Cancel an active A2A task."""
        if task_id not in self.active_tasks:
            return f"Task {task_id} not found or no longer active"
        
        # Cancel monitoring
        if task_id in self.task_monitors:
            future = self.task_monitors[task_id]
            future.cancel()
            del self.task_monitors[task_id]
        
        # Remove from active tasks
        task_info = self.active_tasks.pop(task_id)
        
        # Persist state
        self._save_state()
        
        return f"Cancelled task {task_id} ({task_info.skill_id})"
    
    def get_active_tasks(self) -> Dict[str, A2ATaskInfo]:
        """Get all active tasks."""
        return self.active_tasks.copy()
    
    def cleanup_old_tasks(self):
        """Clean up old completed tasks."""
        now = datetime.now()
        tasks_to_remove = []
        
        for task_id, task_info in self.active_tasks.items():
            if now - task_info.created_at > self.max_task_age:
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            self.cancel_task(task_id)
    
    def _save_state(self):
        """Save active tasks state to disk."""
        try:
            state_data = {
                task_id: task_info.to_dict() 
                for task_id, task_info in self.active_tasks.items()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save A2A state: {e}")
    
    def _load_state(self):
        """Load active tasks state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                
                for task_id, task_dict in state_data.items():
                    task_info = A2ATaskInfo.from_dict(task_dict)
                    self.active_tasks[task_id] = task_info
                    
                    # Restart monitoring for active tasks
                    # Note: In real implementation, would query A2A server to verify task still exists
                    self.task_monitors[task_id] = asyncio.create_task(
                        self._monitor_task(task_id)
                    )
                
                logger.info(f"Loaded {len(self.active_tasks)} active A2A tasks from state")
                
        except Exception as e:
            logger.error(f"Failed to load A2A state: {e}")
            # Continue with empty state
    
    async def shutdown(self):
        """Shutdown the message pump and clean up resources."""
        logger.info("Shutting down A2A message pump")
        
        # Cancel all monitoring tasks gracefully
        # These are concurrent.futures.Future objects from run_coroutine_threadsafe
        for task_id, future in list(self.task_monitors.items()):
            if not future.done():
                future.cancel()
                # For concurrent futures, we can't await them directly
                # Just wait a bit for them to finish
                try:
                    future.result(timeout=0.1)
                except (asyncio.CancelledError, concurrent.futures.CancelledError, TimeoutError):
                    pass  # Expected
                except Exception as e:
                    logger.debug(f"Error cancelling task {task_id}: {e}")
        
        # Clear task monitors
        self.task_monitors.clear()
        
        # Stop the event loop gracefully
        if self._loop and self._loop.is_running():
            # Cancel all tasks in the loop first
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            
            # Schedule loop stop
            self._loop.call_soon_threadsafe(self._loop.stop)
            # Give it a moment to finish
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=1.0)
        
        # Save final state
        self._save_state()
        
        logger.info("A2A message pump shutdown complete")
