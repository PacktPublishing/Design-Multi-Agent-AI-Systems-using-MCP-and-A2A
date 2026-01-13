import importlib

from backend.object_model import Tool
import os
import sys

class Bootstrap(Tool):
    def __init__(self):
        desc = 'Tool to restart the program using execv.'
        super().__init__(
            name='bootstrap',
            description=desc,
            parameters=[],  # No parameters needed for execv
            required=set()
        )

    def run(self, **kwargs):
        main_module = sys.modules['__main__']
        module_path = getattr(main_module, '__file__', None)
        if not module_path:
            raise RuntimeError("Cannot determine __main__.__file__; are you in a REPL or notebook?")

        spec = getattr(main_module, '__spec__', None)

        if spec and spec.name:
            # Executed as a module: python -m package.module
            module_name = spec.name
            args = [sys.executable, '-m', module_name, *sys.argv[1:]]
        else:
            # Executed as a script: python script.py
            args = [sys.executable, module_path, *sys.argv[1:]]

        os.execv(sys.executable, args)
