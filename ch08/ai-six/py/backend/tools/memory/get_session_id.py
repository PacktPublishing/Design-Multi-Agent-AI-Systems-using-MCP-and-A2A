from backend.object_model import Tool

class GetSessionId(Tool):
    """Tool to get the current session ID."""
    
    def __init__(self, engine=None):
        """Initialize the tool.
        
        Args:
            engine: Reference to the Engine instance
        """
        self.engine = engine
        
        super().__init__(
            name='get_session_id',
            description='Get the ID of the current session.',
            parameters=[],
            required=set()
        )
    
    def run(self, **kwargs):
        """Get the current session ID.
        
        Returns:
            String with the current session ID
        """
        if not self.engine:
            return "Error: Engine reference not set."
        
        session_id = self.engine.get_session_id()
        
        return f"Current session ID: {session_id}"
