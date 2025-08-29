#!/bin/bash
# Dominus AI - Service Startup Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[Dominus AI] Starting AI services..."

# Check if Ollama is running
if ! systemctl is-active --quiet ollama; then
    echo "[INFO] Starting Ollama service..."
    sudo systemctl start ollama
    sleep 3
fi

# Check if model is available
if ! ollama list | grep -q "gpt-oss:120b"; then
    echo "[ERROR] Model gpt-oss:120b not found. Please run: ollama pull gpt-oss:120b"
    exit 1
fi

# Stop any existing bridge process
pkill -f "ollama-bridge-v2.py" 2>/dev/null

# Start the bridge service
echo "[INFO] Starting bridge service on port 8090..."
cd "$PROJECT_ROOT/services"
nohup python3 ollama-bridge-v2.py > "$PROJECT_ROOT/logs/bridge.log" 2>&1 &

sleep 2

# Verify bridge is running
if ps aux | grep -v grep | grep -q "ollama-bridge-v2.py"; then
    echo "[SUCCESS] Bridge service started"
    echo "[INFO] Logs available at: $PROJECT_ROOT/logs/bridge.log"
else
    echo "[ERROR] Failed to start bridge service"
    exit 1
fi

# Test the service
echo "[INFO] Testing service health..."
if curl -s http://localhost:8090/health | grep -q "ok"; then
    echo "[SUCCESS] Service is healthy"
else
    echo "[WARNING] Service health check failed"
fi

echo "[Dominus AI] All services started successfully"
echo "[INFO] API endpoint: http://localhost:8090"