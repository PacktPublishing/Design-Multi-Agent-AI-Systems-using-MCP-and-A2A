#!/usr/bin/env python3
"""
GitHub User Activity Analyzer Agent

This agent analyzes GitHub user activity and generates comprehensive reports.
It uses the gh CLI tool to gather information about users, repositories, and contributions.
"""

import sys
import os
import json
from pathlib import Path

# Add the backend modules to the path
# Go up two directories from examples/github-analyzer to reach the 'py' directory  
py_directory = Path(__file__).parent.parent.parent
sys.path.insert(0, str(py_directory))

from backend.agent.agent import Agent

def main():
    if len(sys.argv) != 2:
        print("Usage: python github_analyzer.py <github_username>")
        sys.exit(1)
    
    username = sys.argv[1]
    
    # Load configuration
    config_path = str(Path(__file__).parent / 'config.yaml')
    # Initialize agent with GitHub expert persona
    agent = Agent.from_config_file(config_path)
    
    # Start the analysis
    title = f"🔍 Starting GitHub analysis for user: {username}"
    print(title)
    print("=" * len(title))
    
    # Send the initial analysis request
    response = agent.send_message(f"Analyze the GitHub user '{username}' and provide a comprehensive activity report.")
    
    print(response)
    
    # Keep the conversation going if needed
    while True:
        user_input = input("\n💭 Ask a follow-up question (or 'quit' to exit): ")
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        response = agent.send_message(user_input)
        print(response)

if __name__ == "__main__":
    main()