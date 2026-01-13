from backend.tools.base.command_tool import CommandTool

class Kubectl(CommandTool):
    def __init__(self, user: str | None = None):
        doc_link = "https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands"
        super().__init__(
            command_name='kubectl',
            user=user,
            doc_link=doc_link
        )
