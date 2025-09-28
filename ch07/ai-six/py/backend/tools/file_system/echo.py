import os
import sh
from backend.object_model import Tool, Parameter


class Echo(Tool):
    def __init__(self, user: str | None = None):
        self.user = user

        desc = 'Write content to a file, creating any necessary directories.'
        super().__init__(
            name='echo',
            description=desc,
            parameters=[
                Parameter(name='file_path', type='string', description='The path of the file to write to.'),
                Parameter(name='content', type='string', description='The content to write to the file.')
            ],
            required={'file_path', 'content'}
        )

    def run(self, **kwargs):
        filename = kwargs['file_path']
        content = kwargs['content']

        dir_path = os.path.dirname(filename)

        if self.user is not None:
            sh.sudo('-u', self.user, 'mkdir', '-p', dir_path)
            sh.sudo('-u', self.user, 'tee', filename, _in=content, _out=os.devnull)

            return f"Content written to {filename} as user {self.user}"

        os.makedirs(dir_path, exist_ok=True)
        with open(filename, 'w') as file:
            file.write(content)

        return f"Content written to {filename}"
