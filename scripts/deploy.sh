#!/bin/bash
# Synapse Production Deployment Script
# Usage: ./scripts/deploy.sh [--test | --start | --stop | --status]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SYNAPSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$SYNAPSE_DIR/docker-compose.yml"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python
    if ! command -v python &> /dev/null; then
        log_error "Python not found"
        exit 1
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_warn "Docker not found - some features may not work"
    fi

    # Check .env file
    if [ ! -f "$SYNAPSE_DIR/.env" ]; then
        log_warn ".env file not found - copying from .env.example"
        if [ -f "$SYNAPSE_DIR/.env.example" ]; then
            cp "$SYNAPSE_DIR/.env.example" "$SYNAPSE_DIR/.env"
            log_warn "Please edit .env with your API keys"
        else
            log_error ".env.example not found"
            exit 1
        fi
    fi

    log_info "Prerequisites OK"
}

run_tests() {
    log_info "Running tests..."
    cd "$SYNAPSE_DIR"

    # Unit tests
    log_info "Running unit tests..."
    python -m pytest tests/test_identity_model.py tests/test_oracle_tools.py -q --tb=short

    if [ $? -eq 0 ]; then
        log_info "Unit tests PASSED"
    else
        log_error "Unit tests FAILED"
        exit 1
    fi

    # Integration tests (optional)
    if [ "$RUN_INTEGRATION" = "true" ]; then
        log_info "Running integration tests..."
        RUN_GRAPH_INTEGRATION_TESTS=true python -m pytest tests/test_layer3_graph_population.py -q --tb=short
    fi
}

start_services() {
    log_info "Starting services..."
    cd "$SYNAPSE_DIR"

    # Start FalkorDB if Docker available
    if command -v docker &> /dev/null; then
        if ! docker ps | grep -q falkordb; then
            log_info "Starting FalkorDB..."
            docker run -d --name falkordb -p 6379:6379 falkordb/falkordb:latest 2>/dev/null || true
        fi
    fi

    # Start Synapse MCP Server
    log_info "Starting Synapse MCP Server..."
    python -m synapse.mcp_server &
    echo $! > /tmp/synapse.pid
    log_info "Synapse started (PID: $(cat /tmp/synapse.pid))"
}

stop_services() {
    log_info "Stopping services..."

    if [ -f /tmp/synapse.pid ]; then
        kill $(cat /tmp/synapse.pid) 2>/dev/null || true
        rm /tmp/synapse.pid
    fi

    log_info "Services stopped"
}

check_status() {
    log_info "Checking status..."

    # Check FalkorDB
    if docker ps | grep -q falkordb; then
        log_info "FalkorDB: RUNNING"
    else
        log_warn "FalkorDB: NOT RUNNING"
    fi

    # Check Synapse
    if [ -f /tmp/synapse.pid ] && kill -0 $(cat /tmp/synapse.pid) 2>/dev/null; then
        log_info "Synapse: RUNNING (PID: $(cat /tmp/synapse.pid))"
    else
        log_warn "Synapse: NOT RUNNING"
    fi
}

# Main
case "${1:-}" in
    --test)
        check_prerequisites
        run_tests
        ;;
    --start)
        check_prerequisites
        start_services
        ;;
    --stop)
        stop_services
        ;;
    --status)
        check_status
        ;;
    *)
        echo "Synapse Deployment Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  --test     Run tests before deployment"
        echo "  --start    Start all services"
        echo "  --stop     Stop all services"
        echo "  --status   Check service status"
        echo ""
        echo "Environment:"
        echo "  RUN_INTEGRATION=true  Run integration tests"
        ;;
esac
