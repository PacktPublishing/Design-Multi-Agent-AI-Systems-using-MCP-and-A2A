"""Specialized A2A task management tools."""

from backend.object_model.tool import Tool, Parameter
from backend.a2a_client.a2a_manager import A2AManager


class A2ATaskListTool(Tool):
    """Tool to list active A2A tasks."""
    
    def __init__(self):
        super().__init__(
            name="a2a_list_tasks",
            description="List all active A2A tasks and their status",
            parameters=[],
            required=set()
        )
    
    def run(self, **kwargs) -> str:
        """List all active A2A tasks."""
        message_pump = A2AManager.get_message_pump()
        if not message_pump:
            return "A2A not initialized."
        
        active_tasks = message_pump.get_active_tasks()
        
        if not active_tasks:
            return "No active A2A tasks."
        
        result = f"Active A2A Tasks ({len(active_tasks)}):\\n"
        result += "=" * 40 + "\\n"
        
        for task_id, task_info in active_tasks.items():
            elapsed = (task_info.last_checked - task_info.created_at).total_seconds()
            result += f"• {task_id}\\n"
            result += f"  Server: {task_info.server_name}\\n"
            result += f"  Skill: {task_info.skill_id}\\n"
            result += f"  Status: {task_info.status}\\n"
            result += f"  Running for: {elapsed:.0f}s\\n"
            
            if task_info.user_input_required:
                result += f"  ⚠️ User input required: {task_info.user_input_prompt}\\n"
            
            result += "\\n"
        
        return result


class A2ATaskCancelTool(Tool):
    """Tool to cancel an A2A task."""
    
    def __init__(self):
        super().__init__(
            name="a2a_cancel_task",
            description="Cancel an active A2A task",
            parameters=[
                Parameter(
                    name="task_id",
                    type="string",
                    description="ID of the task to cancel"
                )
            ],
            required={"task_id"}
        )
    
    def run(self, task_id: str, **kwargs) -> str:
        """Cancel the specified A2A task."""
        message_pump = A2AManager.get_message_pump()
        if not message_pump:
            return "A2A not initialized."
        return message_pump.cancel_task(task_id)


class A2ATaskMessageTool(Tool):
    """Tool to send a message to an A2A task."""
    
    def __init__(self):
        super().__init__(
            name="a2a_send_message",
            description="Send a message to an active A2A task", 
            parameters=[
                Parameter(
                    name="task_id",
                    type="string",
                    description="ID of the task to send message to"
                ),
                Parameter(
                    name="message", 
                    type="string",
                    description="Message to send to the task"
                )
            ],
            required={"task_id", "message"}
        )
    
    def run(self, task_id: str, message: str, **kwargs) -> str:
        """Send message to the specified A2A task."""
        import asyncio
        
        message_pump = A2AManager.get_message_pump()
        if not message_pump:
            return "A2A not initialized."
        
        # Use simple pattern like MCP tools
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            return loop.run_until_complete(
                message_pump.send_message_to_task(task_id, message)
            )
        finally:
            loop.close()


class A2ATaskStatusTool(Tool):
    """Tool to get detailed status of an A2A task."""
    
    def __init__(self):
        super().__init__(
            name="a2a_task_status",
            description="Get detailed status of an A2A task",
            parameters=[
                Parameter(
                    name="task_id",
                    type="string", 
                    description="ID of the task to check"
                )
            ],
            required={"task_id"}
        )
    
    def run(self, task_id: str, **kwargs) -> str:
        """Get detailed status of the specified task."""
        message_pump = A2AManager.get_message_pump()
        if not message_pump:
            return "A2A not initialized."
        
        active_tasks = message_pump.get_active_tasks()
        
        if task_id not in active_tasks:
            return f"Task {task_id} not found or no longer active."
        
        task_info = active_tasks[task_id]
        elapsed = (task_info.last_checked - task_info.created_at).total_seconds()
        
        result = f"Task Status: {task_id}\\n"
        result += "=" * 40 + "\\n"
        result += f"Server: {task_info.server_name}\\n"
        result += f"Skill: {task_info.skill_id}\\n"
        result += f"Status: {task_info.status}\\n"
        result += f"Created: {task_info.created_at.strftime('%Y-%m-%d %H:%M:%S')}\\n"
        result += f"Running for: {elapsed:.0f} seconds\\n"
        result += f"Last checked: {task_info.last_checked.strftime('%H:%M:%S')}\\n"
        
        if task_info.last_message_at:
            result += f"Last message: {task_info.last_message_at.strftime('%H:%M:%S')}\\n"
        
        if task_info.user_input_required:
            result += f"\\n⚠️ User Input Required:\\n{task_info.user_input_prompt}\\n"
        
        if task_info.artifacts:
            result += f"\\nArtifacts ({len(task_info.artifacts)}):\\n"
            for artifact in task_info.artifacts:
                result += f"  • {artifact}\\n"
        
        return result