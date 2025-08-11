import shlex

from ..base.command_tool import CommandTool

class Git(CommandTool):
    def __init__(self, user: str | None = None):
        super().__init__(command_name='git', user=user, doc_link='https://git-scm.com/doc')

    def run(self, **kwargs):
        args = shlex.split(kwargs['args'])

        if "--no-pager" not in args:
            args = ["--no-pager"] + args
        return super().run(args=' '.join(args))
