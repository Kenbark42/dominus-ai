# Dominus AI - Advanced AI Service Infrastructure

An independent AI service infrastructure providing context-aware LLM capabilities, RAG (Retrieval Augmented Generation), and extensible knowledge management.

## 🚀 Overview

Dominus AI is a sophisticated standalone AI service that provides:
- **GPT-OSS-120B** model deployment via Ollama (65GB, 8K context)
- **Context-aware conversations** with session persistence
- **RAG system** with ChromaDB for document retrieval
- **TGI-compatible REST API** bridge
- **Extensible plugin architecture** for future capabilities

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     DOMINUS AI PLATFORM                   │
├──────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Ollama    │  │   Context   │  │     RAG     │      │
│  │  GPT-OSS    │◄─┤   Manager   ├─►│   Engine    │      │
│  │    120B     │  │  (SQLite)   │  │ (ChromaDB)  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
│         ▲                │                 │              │
│         └────────────────┼─────────────────┘              │
│                          ▼                                │
│               ┌──────────────────┐                        │
│               │  Context Bridge  │                        │
│               │   (Port 8090)    │                        │
│               └──────────────────┘                        │
│                          │                                │
│                          ▼                                │
│               ┌──────────────────┐                        │
│               │   NGINX Proxy    │                        │
│               │  (Port 8001 SSL) │                        │
│               └──────────────────┘                        │
│                          │                                │
│                          ▼                                │
│                  External Clients                         │
│            (darkfoo.com, other services)                  │
└──────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
/home/ken/ai/dominus-ai/
├── services/
│   ├── context_bridge.py      # Main API server with context awareness
│   ├── context_manager.py     # Session and conversation management
│   ├── rag_engine.py          # RAG system with ChromaDB
│   └── document_ingestion.py  # Document processing pipeline (coming)
├── data/
│   ├── chromadb/              # Vector database storage
│   ├── sessions.db            # SQLite conversation history
│   └── cache/                 # Embedding cache
├── logs/
│   ├── bridge.log             # Service logs
│   └── bridge-error.log       # Error logs
├── docs/
│   └── PHASE3_RAG_ARCHITECTURE.md  # RAG system design
└── scripts/
    └── start-services.sh      # Service management scripts
```

## 🔌 Core Services

### Context Bridge (`context_bridge.py`)
- **Port**: 8090
- **Features**: Context-aware conversations, session management, RAG integration
- **Endpoints**: `/chat`, `/generate`, `/session/*`, `/health`

### Context Manager (`context_manager.py`)
- **Storage**: SQLite database
- **Features**: Session persistence, conversation history, token tracking
- **Capacity**: Unlimited sessions with automatic cleanup

### RAG Engine (`rag_engine.py`)
- **Vector DB**: ChromaDB with persistent storage
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Features**: Document chunking, semantic search, collection management

### Network Configuration
- **Port 8090**: Internal bridge service (TGI-compatible API)
- **Port 11434**: Ollama native API
- **Port 8001**: Public HTTPS endpoint (via nginx proxy)

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