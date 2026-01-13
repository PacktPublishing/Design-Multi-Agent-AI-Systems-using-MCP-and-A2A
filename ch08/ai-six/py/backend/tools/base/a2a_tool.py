from a2a.types import AgentSkill
from backend.object_model.tool import Tool, Parameter
from backend.a2a_client.a2a_manager import A2AManager


class A2ATool(Tool):
    """Tool that communicates with A2A (Agent-to-Agent) servers using async-to-sync pattern."""

    def __init__(self, server_name: str, skill: AgentSkill):
        """Initialize from A2A skill information.

        Args:
            server_name: Name of the A2A server
            skill: Skill object from agent card
        """
        self.server_name = server_name
        self.skill_name = skill.name

        # A2A skills are conversational - create standard parameters
        parameters = [
            Parameter(
                name='message',
                type='string',
                description=f'Natural language request for the `{skill.name}` skill'
            ),
            Parameter(
                name='task_id',
                type='string',
                description='Optional: ID of existing task to send message to'
            )
        ]

        required = {'message'}

        super().__init__(
            name=f"{server_name}_{skill.name}",
            description=skill.description,
            parameters=parameters,
            required=required
        )

    def run(self, **kwargs) -> str:
        """Execute the A2A skill using the A2AExecutor."""
        task_id = kwargs.get('task_id')
        message = kwargs.get('message', '')

        executor = A2AManager.get_executor()
        if not executor:
            return "Error: A2A not initialized. Please configure A2A integration."

        return executor.execute_skill(
            self.server_name,
            self.skill_name,
            message,
            task_id
        )
