
Here is chapter 9 outline from the book.

```
# Overview

https://levelup.gitconnected.com/building-mcp-powered-agentic-rag-application-step-by-step-guide-1-2-efea9fb6f250
https://medium.com/@piyushagni5/building-your-first-a2a-system-a-complete-guide-d293035ceced?sk=46a6eabfc5c1c278642456fce3da002d

# Building an AI-Driven DevOps Team

# Defining Roles and Responsibilities for Specialized Agents

# Implementing the Agents

# Orchestrating the Team with a Manager Agent

# Integrating Human Feedback and Control Channels

# Summary
```

# MAKDO (Multi-Agent Kubernetes DevOps) - System Implementation Plan

## System Architecture

**Built on AI-6 Framework** - Leveraging existing infrastructure:
- Agent framework with session management
- Built-in A2A client/server support
- Native MCP integration
- Slack integration capabilities

## Core Components

### Infrastructure
- **UI**: Slack channel in bot-playground namespace
- **Backend**: Single k8s-ai A2A server with multi-cluster registration
- **Framework**: AI-6 handling all agent communication and tool management

### Agent Configuration (4 specialized AI-6 agents)

#### 1. Coordinator Agent
- **Role**: Main orchestrator with polling logic and task dispatch
- **Tools**: A2A client (to other agents), basic kubectl for status checks
- **System Prompt Focus**: Task orchestration, decision-making, escalation policies

#### 2. Analyzer Agent
- **Role**: Cluster health assessment and problem identification
- **Tools**: A2A client (to k8s-ai server), read-only cluster access
- **System Prompt Focus**: Health assessment, problem prioritization, diagnostic reasoning

#### 3. Fixer Agent
- **Role**: Safe cluster modification operations
- **Tools**: AI-6's built-in kubectl tool, validation commands
- **System Prompt Focus**: Safe operation execution, validation, rollback strategies

#### 4. Slack Agent
- **Role**: User communication and command interface
- **Tools**: Slack MCP server for messaging/notifications
- **System Prompt Focus**: User communication, alert formatting, command parsing

## System Configuration

### Cluster Setup
- Target Kubernetes clusters (names, contexts, kubeconfig paths)
- k8s-ai A2A server with multi-cluster registration via session tokens

### Slack Integration
- **Credentials**: Available in `/Users/gigi/git/ai-six/py/frontend/slack/.env`
- **MCP Server**: Using korotovsky/slack-mcp-server for comprehensive Slack functionality
- **Channel**: Dedicated DevOps channel in bot-playground namespace

### Operational Parameters
- Polling intervals and alert thresholds
- Safety constraints and approval workflows
- Multi-cluster session token management

## Design Focus Areas

1. **Agent System Prompts**: Define personality, decision-making logic, and operational constraints for each agent
2. **Tool Selection**: Configure appropriate tool access per agent role
3. **Communication Patterns**: Define inter-agent message flows and escalation paths
4. **Safety Mechanisms**: Implement validation, approval workflows, and rollback procedures

## Implementation Benefits

- **No Custom Infrastructure**: AI-6 provides all plumbing (agents, A2A, MCP, Slack)
- **Single k8s-ai Server**: Multi-cluster support via session-based registration
- **Built-in Tools**: kubectl, Slack, and A2A communication ready to use
- **Focus on Configuration**: Design effort concentrated on agent prompts and tool selection
