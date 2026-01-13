#!/usr/bin/env python3
"""
Python CLI Program Builder Agent

This agent system builds Python CLI programs using a coordinated multi-agent approach.
It includes a project manager that works with specialized developer and tester sub-agents
to create complete command-line applications.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the backend modules to the path
# Go up two directories from examples/cli-program-builder to reach the 'py' directory  
py_directory = Path(__file__).parent.parent.parent
sys.path.insert(0, str(py_directory))

from backend.agent.agent import Agent
from backend.agent.config import Config

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Python CLI Program Builder - Create Python CLI applications using AI agents'
    )
    parser.add_argument(
        '--output-dir', 
        default=os.environ.get('CLI_PROGRAM_BUILDER_OUTPUT_DIR', '~/cli-python-projects'),
        help='Directory for generated CLI projects (default: ~/cli-python-projects, can be set via CLI_PROGRAM_BUILDER_OUTPUT_DIR env var)'
    )
    args = parser.parse_args()
    
    # Resolve and expand the output directory path
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Projects will be created in: {output_dir}")
    
    # Load configuration
    config_path = str(Path(__file__).parent / 'config.yaml')
    config = Config.from_file(config_path)
    
    # Inject output directory into system prompts
    def inject_output_dir(prompt: str, output_path: str) -> str:
        """Inject the actual output directory path into system prompt."""
        injected = prompt + f"\n\nIMPORTANT: Create all files in the output directory: {output_path}"
        return injected
    
    # Update main agent system prompt
    config.system_prompt = inject_output_dir(config.system_prompt, str(output_dir))
    
    # Update sub-agent system prompts
    for agent_config in config.agents:
        agent_config.system_prompt = inject_output_dir(agent_config.system_prompt, str(output_dir))
    
    # Initialize the project manager agent (which manages the sub-agents)
    agent = Agent(config)
    
    # Start the CLI builder
    title = "🔧 Starting Python CLI Program Builder"
    print(title)
    print("=" * len(title))
    
    # Send the initial greeting and request
    greeting = """Hello! I'm a project manager specializing in building Python CLI programs. 
I work with two expert sub-agents:
- A Python CLI Developer who writes well-structured command-line code
- A Python Tester who ensures quality and creates comprehensive tests

My scope is exclusively Python CLI programs. If you need web apps, desktop applications, 
or programs in other languages, I'll need to respectfully decline and suggest you find 
a specialist for those areas.

What Python CLI program would you like me to help you build today?"""
    
    print("\n" + greeting + "\n")
    
    # Interactive session for building CLI programs
    try:
        while True:
            try:
                user_input = input("📝 Describe your CLI program idea (or 'quit' to exit): ")
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Thanks for using the Python CLI Program Builder!")
                    break
                
                if not user_input.strip():
                    continue
                    
                # Send the user's request to the project manager
                response = agent.send_message(user_input)
                print("\n" + response + "\n")
                
                # Allow follow-up questions and refinements
                while True:
                    try:
                        follow_up = input("💭 Any follow-up questions or modifications? (or 'new' for new project, 'quit' to exit): ")
                        if follow_up.lower() in ['quit', 'exit', 'q']:
                            print("\n👋 Thanks for using the Python CLI Program Builder!")
                            return
                        elif follow_up.lower() in ['new', 'n']:
                            break
                        elif not follow_up.strip():
                            continue
                        
                        response = agent.send_message(follow_up)
                        print("\n" + response + "\n")
                    except KeyboardInterrupt:
                        print("\n\n⏸️  Interrupted. Type 'new' for a new project or 'quit' to exit.")
                        break
                    except EOFError:
                        print("\n\n👋 Thanks for using the Python CLI Program Builder!")
                        return
                        
            except KeyboardInterrupt:
                print("\n\n⏸️  Interrupted. Type 'quit' to exit or describe a new CLI program.")
                continue
            except EOFError:
                print("\n\n👋 Thanks for using the Python CLI Program Builder!")
                break
                
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        print("Please try again or contact support if the issue persists.")
        return

if __name__ == "__main__":
    main()
