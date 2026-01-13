from backend.object_model import Tool, Parameter

class LoadSession(Tool):
    """Tool to load a specific session by ID."""
    
    def __init__(self, engine=None):
        """Initialize the tool.
        
        Args:
            engine: Reference to the Engine instance
        """
        self.engine = engine
        
        super().__init__(
            name='load_session',
            description='Load a specific session by ID.',
            parameters=[
                Parameter(
                    name='session_id',
                    type='string',
                    description='ID of the session to load'
                )
            ],
            required={'session_id'}
        )
    
    def run(self, session_id, **kwargs) -> str:
        """Load a specific session.
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            String indicating success or failure
        """
        if not self.engine:
            return "Error: Engine reference not set."
        
        if not session_id:
            return "Error: Session ID is required."
        
        success = self.engine.load_session(session_id)
        
        if success:
            return f"Successfully loaded session: {session_id}"
        else:
            return f"Failed to load session: {session_id}. Session may not exist."
