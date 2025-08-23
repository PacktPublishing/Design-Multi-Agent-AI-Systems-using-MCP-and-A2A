from backend.object_model import Tool, Parameter
import sh
import shlex

class Kubectl(Tool):
    def __init__(self, user: str | None = None):
        self.user = user

        desc = 'Simple Kubectl tool to interact with Kubernetes clusters.'
        super().__init__(
            name='kubectl',
            description=desc,
            parameters=[Parameter(name='args', type='string', description='command-line arguments for kubectl')],
            required={'args'}
        )

    def run(self, **kwargs):
        args = shlex.split(kwargs['args'])

        # Decide which user to run as (None means run as the current user)
        try:
            if self.user is not None:
                return sh.sudo('-u', self.user, 'kubectl', *args)
            else:
                return sh.kubectl(*args)
        except Exception as e:
            raise