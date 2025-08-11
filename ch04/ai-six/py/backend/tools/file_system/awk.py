from ..base.command_tool import CommandTool

class Awk(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='awk', user=user, doc_link='https://www.gnu.org/software/gawk/manual/gawk.html')
