# MAKDO - Multi-Agent Kubernetes DevOps System

A multi-agent system built on AI-6 framework for autonomous Kubernetes cluster management and DevOps operations.

## Architecture

MAKDO consists of 4 specialized AI-6 agents:

1. **Coordinator Agent** - Main orchestrator and task dispatcher
2. **Analyzer Agent** - Cluster health assessment using k8s-ai A2A server
3. **Fixer Agent** - Safe cluster modification operations
4. **Slack Agent** - User communication and notification interface

## Features

- **Multi-Cluster Support** - Manage multiple Kubernetes clusters from a single system
- **Autonomous Operations** - Self-healing and proactive cluster management
- **Slack Integration** - Natural language interaction via Slack channels
- **Safety-First** - Validation and approval workflows for critical operations
- **Session-Based** - Secure cluster access via k8s-ai session tokens

## Prerequisites

1. **Kubernetes Clusters** - Local kind clusters or any Kubernetes clusters
2. **OpenAI API Key** - For AI-6 agent operations
3. **Slack Bot Credentials** - For Slack integration (optional)
4. **Go** - For building Slack MCP server
5. **Node.js/npm** - For potential npm packages

## Complete Setup Instructions

### 1. Environment Setup

```bash
# Clone and setup
cd ch09/makdo

# Install dependencies
uv sync

# Copy and configure environment
cp .env.example .env
# Edit .env with your OpenAI API key

# Copy and configure system settings
cp config/makdo.example.yaml config/makdo.yaml
# Edit config/makdo.yaml with your cluster settings
```

### 2. Kubernetes Clusters Setup

```bash
# Create test clusters (if not exists)
kind create cluster --name k8s-ai
kind create cluster --name makdo-test

# Verify clusters
kubectl config get-contexts
```

### 3. Slack MCP Server Setup

The Slack MCP server is already built and included in `bin/slack-mcp-server`.

If you need to rebuild it:
```bash
# Clone and build Slack MCP server
git clone https://github.com/korotovsky/slack-mcp-server.git /tmp/slack-mcp-server
cd /tmp/slack-mcp-server
make build

# Copy binary to MAKDO
cp build/slack-mcp-server /path/to/makdo/bin/slack-mcp-server
chmod +x bin/slack-mcp-server
```

### 4. k8s-ai A2A Server Setup

Start the k8s-ai server in a separate terminal:
```bash
cd /Users/gigi/git/k8s-ai
uv run k8s-ai-server --context kind-k8s-ai
```

The server will be available at `http://localhost:9999`.

### 5. Run MAKDO

```bash
# Start MAKDO system
uv run makdo
```

## Configuration Files

### `.env`
Contains environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `AI6_BOT_TOKEN` - Slack bot token (if using Slack)
- `K8S_AI_BASE_URL` - k8s-ai server URL
- Other Slack and system configuration

### `config/makdo.yaml`
System configuration:
- Kubernetes cluster definitions
- Agent configurations and system prompts
- Operational parameters and safety constraints
- Slack channel and notification settings

## Usage

Once running, MAKDO will:

1. **Monitor Clusters** - Continuously check cluster health every 5 minutes
2. **Analyze Issues** - Use k8s-ai to identify and prioritize problems
3. **Coordinate Fixes** - Dispatch safe remediation actions
4. **Notify Users** - Send alerts and status updates via Slack
5. **Require Approval** - Request human approval for critical operations

## System Components

### Built-in Tools
- **AI-6 kubectl tool** - For cluster operations
- **Slack MCP server** - For Slack communication
- **k8s-ai A2A integration** - For cluster analysis

### Directory Structure
```
makdo/
├── README.md              # This file
├── pyproject.toml         # Dependencies and build config
├── .env                   # Environment variables
├── config/
│   ├── makdo.yaml         # System configuration
│   └── makdo.example.yaml # Configuration template
├── bin/
│   └── slack-mcp-server   # Slack MCP server binary
├── src/makdo/
│   ├── main.py           # Main orchestrator
│   ├── agents/           # Agent configurations
│   ├── tools/            # Custom tools
│   └── mcp_tools/        # MCP tool configurations
└── data/
    └── memory/           # Agent session data
```

## Troubleshooting

### Common Issues

1. **Missing OpenAI API Key**
   - Set `OPENAI_API_KEY` in `.env` file

2. **k8s-ai Server Not Running**
   - Start with: `uv run k8s-ai-server --context kind-k8s-ai`

3. **Kubernetes Clusters Not Found**
   - Check: `kubectl config get-contexts`
   - Create with: `kind create cluster --name <cluster-name>`

4. **Permission Issues**
   - Ensure `bin/slack-mcp-server` is executable: `chmod +x bin/slack-mcp-server`

### Logs and Debugging

MAKDO logs are written to console and optionally to `logs/makdo.log`.
Set `logging.level: "DEBUG"` in `config/makdo.yaml` for verbose output.

## Development

To modify agent behavior:
1. Edit agent configurations in `src/makdo/agents/`
2. Modify system prompts and tool selections
3. Update operational parameters in `config/makdo.yaml`
4. Restart MAKDO to apply changes