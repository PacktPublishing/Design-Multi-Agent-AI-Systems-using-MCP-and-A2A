"""CLI interface for k8s-ai."""

import argparse
import sys

from ..core.kubectl import KubectlExecutor


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Interactive Kubernetes Chat')
    parser.add_argument('--context', '-c', help='Kubernetes context to use')
    args = parser.parse_args()
    
    if not args.context:
        print("Error: Kubernetes context is required!")
        print("Usage: k8s-ai-cli --context <kube context>")
        sys.exit(1)
    
    kubectl_executor = KubectlExecutor(context=args.context)
    
    msg = f"☸️ Interactive Kubernetes Chat (using context: {args.context}). Type 'exit' to quit."
    print(f"{msg}\n{'-' * len(msg)}")
    
    messages = [{'role': 'system', 'content': 'You are a Kubernetes expert ready to help'}]
    
    while (user_input := input("👤 You: ")).lower() != 'exit':
        messages.append(dict(role="user", content=user_input))
        response = kubectl_executor.send_message(messages)
        print(f"🤖 AI: {response}\n----------")


if __name__ == "__main__":
    main()