from ..base.command_tool import CommandTool

class Cat(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='cat', user=user, doc_link='https://www.gnu.org/software/coreutils/manual/html_node/cat-invocation.html')
