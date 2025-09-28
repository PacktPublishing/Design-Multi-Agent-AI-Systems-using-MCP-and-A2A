#!/bin/bash
set -e

# MAKDO E2E Test Runner
# Comprehensive test suite for the Multi-Agent Kubernetes DevOps System

echo "🚀 MAKDO E2E Test Runner"
echo "========================"

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."

    # Check if required tools are installed
    local tools=("kubectl" "kind" "docker" "uv")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            error "$tool is not installed or not in PATH"
            exit 1
        fi
    done

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        error "Docker is not running. Please start Docker and try again."
        exit 1
    fi

    # Check if .env file exists
    if [[ ! -f .env ]]; then
        error ".env file not found. Please copy .env.example to .env and configure."
        exit 1
    fi

    # Check if OPENAI_API_KEY is set
    source .env
    if [[ -z "$OPENAI_API_KEY" ]]; then
        error "OPENAI_API_KEY not set in .env file"
        exit 1
    fi

    success "Prerequisites check passed"
}

# Setup test clusters
setup_clusters() {
    log "Setting up test clusters..."

    local clusters=("k8s-ai" "makdo-test")
    for cluster in "${clusters[@]}"; do
        if kind get clusters | grep -q "^${cluster}$"; then
            log "Cluster kind-${cluster} already exists"
        else
            log "Creating cluster kind-${cluster}..."
            kind create cluster --name "$cluster" --wait 60s
            if [[ $? -eq 0 ]]; then
                success "Created cluster kind-${cluster}"
            else
                error "Failed to create cluster kind-${cluster}"
                exit 1
            fi
        fi
    done

    # Verify cluster contexts
    kubectl config get-contexts | grep -E "(kind-k8s-ai|kind-makdo-test)" || {
        error "Required cluster contexts not found"
        exit 1
    }

    success "Test clusters are ready"
}

# Start supporting services
start_services() {
    log "Starting supporting services..."

    # Check if k8s-ai server is already running
    if curl -s http://localhost:9999/health &> /dev/null; then
        log "k8s-ai server already running"
    else
        log "Starting k8s-ai server..."
        if [[ -d "/Users/gigi/git/k8s-ai" ]]; then
            cd /Users/gigi/git/k8s-ai
            nohup uv run k8s-ai-server --context kind-k8s-ai --port 9999 > /tmp/k8s-ai-server.log 2>&1 &
            K8S_AI_PID=$!
            cd "$SCRIPT_DIR"

            # Wait for server to start
            log "Waiting for k8s-ai server to start..."
            for i in {1..30}; do
                if curl -s http://localhost:9999/health &> /dev/null; then
                    success "k8s-ai server started (PID: $K8S_AI_PID)"
                    break
                fi
                sleep 2
            done

            if ! curl -s http://localhost:9999/health &> /dev/null; then
                error "k8s-ai server failed to start"
                cat /tmp/k8s-ai-server.log
                exit 1
            fi
        else
            warning "k8s-ai directory not found, skipping server start"
        fi
    fi
}

# Run the E2E test
run_test() {
    log "Running MAKDO E2E test..."

    # Ensure test directories exist
    mkdir -p tests/e2e

    # Run the test with timeout (use gtimeout on macOS if available, otherwise plain run)
    if command -v gtimeout &> /dev/null; then
        gtimeout 1800 uv run python tests/e2e/test_makdo_e2e.py
    elif command -v timeout &> /dev/null; then
        timeout 1800 uv run python tests/e2e/test_makdo_e2e.py
    else
        # No timeout command available, run without timeout
        uv run python tests/e2e/test_makdo_e2e.py
    fi
    local test_exit_code=$?

    if [[ $test_exit_code -eq 0 ]]; then
        success "E2E test completed successfully"
        return 0
    elif [[ $test_exit_code -eq 124 ]]; then
        error "E2E test timed out after 30 minutes"
        return 1
    else
        error "E2E test failed with exit code $test_exit_code"
        return 1
    fi
}

# Display results
show_results() {
    log "Test Results Summary"
    echo "===================="

    if [[ -f tests/e2e/results.json ]]; then
        log "Detailed results:"
        cat tests/e2e/results.json | jq '.' 2>/dev/null || cat tests/e2e/results.json
    else
        warning "Results file not found"
    fi

    if [[ -f tests/e2e/makdo_e2e.log ]]; then
        log "Recent log entries:"
        tail -20 tests/e2e/makdo_e2e.log
    fi
}

# Cleanup function
cleanup() {
    log "Cleaning up..."

    # Kill background processes if they exist
    if [[ -n "$K8S_AI_PID" ]]; then
        if kill -0 "$K8S_AI_PID" 2>/dev/null; then
            log "Stopping k8s-ai server (PID: $K8S_AI_PID)"
            kill "$K8S_AI_PID" 2>/dev/null || true
        fi
    fi

    # Kill any remaining MAKDO processes
    pkill -f "makdo" 2>/dev/null || true

    # Clean up test namespaces
    kubectl --context kind-makdo-test delete namespace makdo-test --ignore-not-found=true --wait=false 2>/dev/null || true

    # Clean up temp files
    rm -f /tmp/makdo-test-*.yaml 2>/dev/null || true
    rm -f /tmp/k8s-ai-server.log 2>/dev/null || true

    log "Cleanup completed"
}

# Handle script termination
trap cleanup EXIT INT TERM

# Parse command line arguments
SKIP_SETUP=false
KEEP_CLUSTERS=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-setup)
            SKIP_SETUP=true
            shift
            ;;
        --keep-clusters)
            KEEP_CLUSTERS=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-setup     Skip cluster setup (assume clusters exist)"
            echo "  --keep-clusters  Don't delete clusters after test"
            echo "  --verbose        Enable verbose output"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Enable verbose output if requested
if [[ "$VERBOSE" == "true" ]]; then
    set -x
fi

# Main execution flow
main() {
    log "Starting MAKDO E2E Test Suite"

    # Step 1: Check prerequisites
    check_prerequisites

    # Step 2: Setup clusters (unless skipped)
    if [[ "$SKIP_SETUP" != "true" ]]; then
        setup_clusters
    else
        log "Skipping cluster setup"
    fi

    # Step 3: Start supporting services
    start_services

    # Step 4: Run the actual E2E test
    if run_test; then
        success "All tests passed! 🎉"
        EXIT_CODE=0
    else
        error "Some tests failed 😞"
        EXIT_CODE=1
    fi

    # Step 5: Show results
    show_results

    # Step 6: Cleanup clusters (unless keeping them)
    if [[ "$KEEP_CLUSTERS" != "true" ]]; then
        log "Cleaning up test clusters..."
        kind delete cluster --name k8s-ai 2>/dev/null || true
        kind delete cluster --name makdo-test 2>/dev/null || true
        success "Test clusters cleaned up"
    else
        log "Keeping test clusters as requested"
    fi

    return $EXIT_CODE
}

# Run main function
main "$@"