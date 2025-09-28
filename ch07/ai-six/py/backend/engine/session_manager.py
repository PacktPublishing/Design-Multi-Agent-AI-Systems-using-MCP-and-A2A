import os
import json


class SessionManager:
    def __init__(self, memory_dir: str):
        self.memory_dir = memory_dir

    def set_title(self, session_id: str, title: str):
        """Set the title of a session."""
        sessions = self.list_sessions()
        if session_id not in sessions:
            raise RuntimeError(f"Session {session_id} not found.")

        filename = sessions[session_id]['filename']
        with open(filename, 'r+') as f:
            data = json.load(f)
            data['title'] = title
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()


    def list_sessions(self) -> dict[str, dict]:
        """List all sessions in the memory directory.
        
        Returns:
            A dictionary mapping session IDs to tuples of (name, filename)
        """
        sessions = {}
        files = os.listdir(self.memory_dir)
        for f in files:
            if f.endswith('.json'):
                try:
                    # Get session ID from the filename (dropping the .json extension)
                    session_id = os.path.basename(f).rsplit('.json', 1)[0]
                    
                    # Try to open and parse the file to verify it's valid JSON
                    full_path = os.path.join(self.memory_dir, f)
                    with open(full_path, 'r') as file:
                        try:
                            # Attempt to parse the JSON
                            session = json.loads(file.read())
                            # Only add if we could parse the JSON
                            sessions[session_id] = dict(title=session['title'], filename=full_path)
                        except json.JSONDecodeError:
                            # Skip files with invalid JSON
                            print(f"Skipping file with invalid JSON: {f}")
                            continue
                except Exception as e:
                    # Skip any files that cause other errors
                    print(f"Error parsing session file {f}: {e}")
                    continue
                    
        return sessions

    def delete_session(self, session_id: str):
        """Delete a session by its ID."""
        sessions = self.list_sessions()
        if session_id not in sessions:
            raise RuntimeError(f"Session {session_id} not found.")

        filename = sessions[session_id]['filename']
        os.remove(filename)
