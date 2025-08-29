# Dominus AI

An independent AI service infrastructure providing LLM capabilities through a unified API endpoint.

## Overview

Dominus AI is a standalone AI service that provides:
- GPT-OSS-120B model deployment via Ollama
- TGI-compatible REST API bridge
- Model management and orchestration
- Tool integration capabilities

## Architecture

```
┌─────────────────────────────────────┐
│         External Clients            │
│    (darkfoo.com, other services)    │
└────────────┬────────────────────────┘
             │
             ▼
     ┌───────────────┐
     │  HTTPS/8001   │
     │   (nginx)     │
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │  Bridge/8090  │
     │  (Python)     │
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │ Ollama/11434  │
     │   (LLM API)   │
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │  GPT-OSS-120B │
     │    (Model)    │
     └───────────────┘
```

## Components

### Services
- **ollama-bridge-v2.py**: Main TGI-compatible bridge service (port 8090)
- **ollama-bridge-tools.py**: Tool-enhanced bridge for function calling
- **tool_system.py**: Tool integration and management system

### Configuration
- Port 8090: Bridge service (TGI-compatible API)
- Port 11434: Ollama native API
- Port 8001: Public HTTPS endpoint (via nginx proxy)

## Installation

1. Install Ollama:
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

2. Pull the model:
```bash
ollama pull gpt-oss:120b
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Start services:
```bash
./scripts/start-services.sh
```

## API Usage

### Generate Text
```bash
curl -X POST https://api.darkfoo.com:8001/generate \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": "Hello, how are you?",
    "parameters": {
      "max_new_tokens": 100,
      "temperature": 0.7
    }
  }'
```

### Health Check
```bash
curl https://api.darkfoo.com:8001/health
```

## Development

This project is designed to be service-agnostic and can be integrated with any application requiring LLM capabilities.

### Directory Structure
```
dominus-ai/
├── services/       # Core service implementations
├── configs/        # Configuration files
├── scripts/        # Utility and deployment scripts
├── models/         # Model-specific configurations
├── logs/          # Service logs
└── docs/          # Documentation
```

## License

MIT

## Author

Ken - 2025