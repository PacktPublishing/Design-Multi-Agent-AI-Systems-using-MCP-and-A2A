from ..base.command_tool import CommandTool

class Patch(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='patch', user=user, doc_link='https://www.gnu.org/software/diffutils/manual/html_node/patch-Invocation.html')
