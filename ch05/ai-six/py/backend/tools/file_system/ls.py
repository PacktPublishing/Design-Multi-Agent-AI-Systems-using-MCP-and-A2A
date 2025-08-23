from backend.tools.base.command_tool import CommandTool

class Ls(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='ls', user=user, doc_link='https://www.gnu.org/software/coreutils/manual/html_node/ls-invocation.html')
