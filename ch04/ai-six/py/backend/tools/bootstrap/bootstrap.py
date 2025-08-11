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
        try:
            # Infer module name from __main__ context
            main_module = sys.modules['__main__']
            module_path = getattr(main_module, '__file__', None)
            if not module_path:
                raise RuntimeError("Can't determine main module file")

            # Handle both module and direct file execution
            if hasattr(main_module, '__package__') and main_module.__package__:
                # Module execution (python -m package.module)
                spec = importlib.util.find_spec(main_module.__package__)
                if spec is None:
                    raise RuntimeError("Cannot resolve package for restart")
                    
                module_name = f"{main_module.__package__}.{os.path.basename(module_path).split('.')[0]}"
                os.execv(sys.executable, [sys.executable, "-m", module_name, *sys.argv[1:]])
            else:
                # Direct file execution (python file.py)
                os.execv(sys.executable, [sys.executable, module_path, *sys.argv[1:]])

        except Exception as e:
            raise RuntimeError(f"Failed to restart: {e}") from e