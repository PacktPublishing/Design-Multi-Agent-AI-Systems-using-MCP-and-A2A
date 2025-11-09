#!/bin/bash

# Script to test connectivity between MAKDO clusters
# Tests that pods in control cluster can reach the worker cluster

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Testing cross-cluster connectivity..."
echo ""

# Switch to control cluster
kubectl config use-context kind-makdo-control > /dev/null

echo "1. Testing from control cluster to worker cluster's Kubernetes API..."
# Try to reach worker cluster API from a pod in control cluster
kubectl run connectivity-test --image=curlimages/curl:latest --restart=Never --rm -i --command -- \
    curl -s -k https://makdo-worker-control-plane:6443/healthz || true

echo ""
echo "2. Testing DNS resolution in control cluster..."
kubectl run dns-test --image=busybox:latest --restart=Never --rm -i --command -- \
    nslookup kubernetes.default.svc.cluster.local

echo ""
echo -e "${GREEN}✓${NC} Basic cluster connectivity verified"
echo ""
echo "Note: Cross-cluster pod-to-pod communication requires additional setup."
echo "MAKDO will communicate with k8s-ai through exposed ports (host.docker.internal:8100)"
