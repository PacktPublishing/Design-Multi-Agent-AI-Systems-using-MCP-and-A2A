from backend.tools.base.command_tool import CommandTool

class Sed(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='sed', user=user, doc_link='https://www.gnu.org/software/sed/manual/sed.html')
