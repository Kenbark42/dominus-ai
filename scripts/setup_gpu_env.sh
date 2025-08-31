#!/bin/bash

# Setup GPU environment for Ollama with AMD Radeon 8060S
echo "Setting up GPU environment variables..."

# Create systemd override directory for ollama
sudo mkdir -p /etc/systemd/system/ollama.service.d/

# Create override configuration
sudo tee /etc/systemd/system/ollama.service.d/gpu.conf > /dev/null << 'EOF'
[Service]
# AMD GPU Configuration for Radeon 8060S
Environment="HSA_OVERRIDE_GFX_VERSION=11.0.0"
Environment="ROCR_VISIBLE_DEVICES=0"
Environment="HIP_VISIBLE_DEVICES=0"
Environment="GPU_MAX_HW_QUEUES=8"
Environment="GPU_MAX_ALLOC_PERCENT=95"

# Ollama GPU settings
Environment="OLLAMA_NUM_GPU=999"
Environment="OLLAMA_GPU_MEMORY_FRACTION=0.95"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=60m"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_NUM_PARALLEL=4"

# Memory settings for large models
Environment="OLLAMA_MAX_VRAM=120000"
EOF

echo "Reloading systemd configuration..."
sudo systemctl daemon-reload

echo "Restarting Ollama with GPU support..."
sudo systemctl restart ollama

sleep 3

echo "Checking Ollama status..."
sudo systemctl status ollama --no-pager | head -10

echo ""
echo "Testing GPU acceleration..."
echo "This should be much faster than before:"
time curl -s http://localhost:11434/api/generate -d '{
  "model": "gpt-oss:120b",
  "prompt": "Say hello",
  "stream": false,
  "options": {
    "num_ctx": 32768,
    "num_predict": 10
  }
}' | python3 -c "import json, sys; data=json.load(sys.stdin); print('Response:', data.get('response', 'No response')[:100]); print('Total duration:', data.get('total_duration', 0)/1000000000, 'seconds')"

echo ""
echo "GPU environment setup complete!"