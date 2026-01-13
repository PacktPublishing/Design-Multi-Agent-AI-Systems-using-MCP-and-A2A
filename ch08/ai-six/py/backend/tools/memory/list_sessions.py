import json

from backend.object_model import Tool

class ListSessions(Tool):
    """Tool to list all available sessions in memory."""
    
    def __init__(self, engine=None):
        """Initialize the tool.
        
        Args:
            engine: Reference to the Engine instance
        """
        self.engine = engine
        
        super().__init__(
            name='list_sessions',
            description='List all available sessions in memory.',
            parameters=[],
            required=set()
        )
    
    def run(self, **kwargs):
        """List all available sessions.
        
        Returns:
            String with the details of all stored sessions (id, title and filename)
        """
        if not self.engine:
            return "Error: Engine reference not set."
        
        sessions = self.engine.list_sessions()
        
        if not sessions:
            return "No sessions found in memory."
        
        return "Available sessions:\n" + json.dumps(sessions)
