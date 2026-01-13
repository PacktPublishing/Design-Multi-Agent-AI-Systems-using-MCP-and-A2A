from backend.object_model import Tool, Parameter

class DeleteSession(Tool):
    """Tool to delete a specific session by ID."""
    
    def __init__(self, engine=None):
        """Initialize the tool.
        
        Args:
            engine: Reference to the Engine instance
        """
        self.engine = engine
        
        super().__init__(
            name='delete_session',
            description='Delete a specific session by ID.',
            parameters=[
                Parameter(
                    name='session_id',
                    type='string',
                    description='ID of the session to delete'
                )
            ],
            required={'session_id'}
        )
    
    def run(self, session_id, **kwargs):
        """Delete a specific session.
        
        Args:
            session_id: ID of the session to delete
            
        Returns:
            String indicating success or failure
        """
        if not self.engine:
            return "Error: Engine reference not set."
        
        if not session_id:
            return "Error: Session ID is required."
        
        # Don't allow deleting the current session
        if session_id == self.engine.get_session_id():
            return "Error: Cannot delete the current active session."
        
        success = self.engine.delete_session(session_id)
        
        if success:
            return f"Successfully deleted session: {session_id}"
        else:
            return f"Failed to delete session: {session_id}. Session may not exist."
