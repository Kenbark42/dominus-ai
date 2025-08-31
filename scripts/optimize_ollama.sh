#!/bin/bash

# Optimize Ollama for AMD Radeon 8060S and Large Models
echo "Optimizing Ollama for GPU acceleration and large context..."

# Stop current services
echo "Stopping services..."
sudo systemctl stop dominus-ai
sudo systemctl stop ollama

# Set environment variables for AMD GPU
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export ROCR_VISIBLE_DEVICES=0
export HIP_VISIBLE_DEVICES=0
export GPU_MAX_HW_QUEUES=8
export GPU_MAX_ALLOC_PERCENT=95

# Restart Ollama with optimized settings
echo "Starting Ollama with GPU acceleration..."
sudo systemctl set-environment HSA_OVERRIDE_GFX_VERSION=11.0.0
sudo systemctl set-environment ROCR_VISIBLE_DEVICES=0
sudo systemctl set-environment OLLAMA_NUM_GPU=999  # Use all available GPU layers
sudo systemctl set-environment OLLAMA_GPU_MEMORY_FRACTION=0.95
sudo systemctl set-environment OLLAMA_MAX_LOADED_MODELS=1
sudo systemctl set-environment OLLAMA_KEEP_ALIVE=60m

# Start Ollama
sudo systemctl start ollama
sleep 5

# Verify GPU support
echo "Checking GPU support..."
ollama list

# Test model with GPU
echo "Testing model performance..."
time ollama run gpt-oss:120b "Say hello" --verbose

echo "Done! Ollama should now be using GPU acceleration."
echo ""
echo "To make these changes permanent, add to /etc/environment:"
echo "HSA_OVERRIDE_GFX_VERSION=11.0.0"
echo "OLLAMA_NUM_GPU=999"
echo "OLLAMA_GPU_MEMORY_FRACTION=0.95"