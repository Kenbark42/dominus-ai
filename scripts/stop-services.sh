#!/bin/bash
# Dominus AI - Service Shutdown Script

echo "[Dominus AI] Stopping AI services..."

# Stop bridge service
if pkill -f "ollama-bridge-v2.py"; then
    echo "[INFO] Bridge service stopped"
else
    echo "[INFO] Bridge service was not running"
fi

# Optionally stop Ollama (commented out by default to keep models loaded)
# echo "[INFO] Stopping Ollama service..."
# sudo systemctl stop ollama

echo "[Dominus AI] Services stopped"