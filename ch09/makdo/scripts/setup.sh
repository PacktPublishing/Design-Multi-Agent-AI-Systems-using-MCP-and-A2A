#!/bin/bash

# MAKDO Setup Script
# Sets up the development environment and creates necessary directories

set -e

echo "🚀 Setting up MAKDO - Multi-Agent Kubernetes DevOps System"

# Create necessary directories
mkdir -p logs
mkdir -p data/sessions
mkdir -p data/history

# Copy configuration files if they don't exist
if [ ! -f config/makdo.yaml ]; then
    echo "📝 Creating configuration file..."
    cp config/makdo.example.yaml config/makdo.yaml
    echo "✅ Created config/makdo.yaml - please customize it"
else
    echo "✅ Configuration file already exists"
fi

if [ ! -f .env ]; then
    echo "📝 Creating environment file..."
    cp .env.example .env
    echo "✅ Created .env - please configure your API keys"
else
    echo "✅ Environment file already exists"
fi

# Install dependencies
echo "📦 Installing dependencies with uv..."
uv sync

# Create kind clusters for testing
echo "🐳 Setting up test Kubernetes clusters..."

# Check if kind-k8s-ai exists
if kind get clusters | grep -q "k8s-ai"; then
    echo "✅ kind-k8s-ai cluster already exists"
else
    echo "🏗️  Creating kind-k8s-ai cluster..."
    kind create cluster --name k8s-ai
fi

# Create second cluster for multi-cluster demo
if kind get clusters | grep -q "makdo-test"; then
    echo "✅ kind-makdo-test cluster already exists"
else
    echo "🏗️  Creating kind-makdo-test cluster..."
    kind create cluster --name makdo-test
fi

echo ""
echo "🎉 MAKDO setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/makdo.yaml with your cluster and Slack settings"
echo "2. Edit .env with your API keys"
echo "3. Start the k8s-ai A2A server: uv run k8s-ai-server --context kind-k8s-ai"
echo "4. Start MAKDO: uv run makdo"
echo ""
echo "Available clusters:"
kind get clusters
echo ""
echo "Check kubectl contexts:"
kubectl config get-contexts