from ..base.command_tool import CommandTool

class Ollama(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='ollama', user=user, doc_link='https://ollama.com/docs')
