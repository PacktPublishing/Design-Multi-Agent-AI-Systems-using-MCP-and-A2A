import sh
import shlex
from backend.object_model import Tool, Parameter

class CommandTool(Tool):
    def __init__(self, command_name: str, user: str | None = None, doc_link: str = ""):
        self.command_name = command_name
        self.user = user
        description = f'{command_name} tool. ' + f'See {doc_link}' if doc_link else ''
        parameters = [Parameter(name='args', type='string', description=f'command-line arguments for {command_name}')]
        required = {'args'}
        super().__init__(
            name=command_name,
            description=description,
            parameters=parameters,
            required=required
        )

    def run(self, **kwargs):
        args = shlex.split(kwargs['args'])
        if self.user is not None:
            return sh.sudo('-u', self.user, self.command_name, *args)
        else:
            return getattr(sh, self.command_name)(*args)
