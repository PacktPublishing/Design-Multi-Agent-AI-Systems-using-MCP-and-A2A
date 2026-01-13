from backend.tools.base.command_tool import CommandTool

class AWS(CommandTool):
    def __init__(self, user: str | None = None):
        doc_link = "https://docs.aws.amazon.com/cli/latest/"
        super().__init__(
            command_name='aws',
            user=user,
            doc_link=doc_link
        )
