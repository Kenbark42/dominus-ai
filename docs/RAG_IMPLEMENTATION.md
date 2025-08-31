# Dominus AI - RAG System Implementation

## Overview
The Retrieval Augmented Generation (RAG) system has been successfully implemented and integrated into the Dominus AI infrastructure. This system enhances the AI's capabilities by providing access to ingested documents and code for context-aware responses.

## System Architecture

### Core Components

1. **RAG Engine** (`/home/ken/ai/dominus-ai/services/rag_engine.py`)
   - ChromaDB vector database for document storage
   - Sentence-transformers for embeddings (all-MiniLM-L6-v2)
   - Document chunking (512 tokens, 50 overlap)
   - Semantic search with adjustable similarity threshold (0.3)

2. **Context Bridge** (`/home/ken/ai/dominus-ai/services/context_bridge.py`)
   - RAG-enhanced endpoints integration
   - Session management with SQLite persistence
   - Multi-endpoint API server on port 8090

3. **Document Ingestion** (`/home/ken/ai/dominus-ai/scripts/ingest_documents.py`)
   - Batch document processing
   - Support for multiple file formats
   - Collection-based organization

## API Endpoints

### RAG-Specific Endpoints

- **POST /chat/rag** - RAG-enhanced chat with document context
- **POST /ingest** - Ingest documents into vector database
- **POST /search** - Semantic search across documents
- **GET /collections** - List available document collections

### Context Management Endpoints

- **POST /chat** - Context-aware chat with session persistence
- **POST /generate** - Legacy endpoint with context support
- **POST /session/create** - Create new conversation session
- **POST /session/info** - Get session information
- **GET /health** - Health check with system status

## Current Collections

| Collection | Documents | Purpose |
|------------|-----------|---------|
| dominus_code | 48 chunks | Dominus AI source code |
| dominus_docs | 15 chunks | Documentation files |
| darkfoo_ai | 80 chunks | Darkfoo AI integration code |
| test | 1 chunk | Test collection |
| documentation | 1 chunk | Additional docs |

**Total: 145 document chunks across 5 collections**

## Darkfoo Integration

### Terminal Commands
The RAG system is fully integrated into the Darkfoo terminal with the following commands:

```bash
rag search <query>    # Search documents
rag ask <question>    # Ask with document context
rag collections       # List document collections
rag status           # Show RAG system status
rag help            # Show help

# Shortcuts
search <query>       # Alias for rag search
ask <question>       # Alias for rag ask
```

### Implementation Files
- `/home/ken/darkfoo/Darkfoo/js/ai/rag-commands.js` - Terminal command implementation
- `/home/ken/darkfoo/Darkfoo/js/ai/context-ai-system.js` - Context management integration
- `/home/ken/darkfoo/Darkfoo/js/ai-command-bridge.js` - AI command bridge

## Configuration

### RAG Engine Settings
```python
{
    'persist_dir': '/home/ken/ai/dominus-ai/data/chromadb',
    'cache_dir': '/home/ken/ai/dominus-ai/data/cache',
    'embedding_model': 'all-MiniLM-L6-v2',
    'chunk_size': 512,
    'chunk_overlap': 50,
    'max_results': 5,
    'similarity_threshold': 0.3,  # Lowered for better recall
    'collection_prefix': 'dominus_'
}
```

### Key Optimizations
1. **Similarity Threshold**: Reduced from 0.7 to 0.3 for better document recall
2. **Chunk Size**: 512 tokens balances context and relevance
3. **Collection Prefix**: All collections use 'dominus_' prefix for organization
4. **Metadata**: Always includes source, filename, type, and timestamp

## Usage Examples

### Document Ingestion
```bash
# Ingest single file
python3 /home/ken/ai/dominus-ai/scripts/ingest_documents.py file.py -c code

# Ingest directory recursively
python3 /home/ken/ai/dominus-ai/scripts/ingest_documents.py /path/to/docs -c docs -r -p "*.md"

# List collections
python3 /home/ken/ai/dominus-ai/scripts/ingest_documents.py --list-collections
```

### API Usage
```bash
# Search documents
curl -X POST https://api.darkfoo.com:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "context management", "collection": "dominus_code", "k": 3}'

# RAG-enhanced chat
curl -X POST https://api.darkfoo.com:8001/chat/rag \
  -H "Content-Type: application/json" \
  -d '{"message": "How does the context manager work?", "collection": "dominus_code"}'

# List collections
curl https://api.darkfoo.com:8001/collections
```

### Terminal Usage
```bash
# In Darkfoo terminal
rag search "session management"
rag ask "How does the RAG engine handle document chunking?"
rag collections
rag status
```

## System Status

### Service Health
- **Dominus AI Service**: ✓ Running (systemd)
- **RAG Engine**: ✓ Available
- **ChromaDB**: ✓ Operational
- **Collections**: 5 active
- **Documents**: 145 chunks indexed

### Recent Activity
- Successfully ingested dominus-ai source code (48 chunks)
- Ingested documentation files (15 chunks)
- Integrated darkfoo AI code (80 chunks)
- Deployed to production with full terminal integration

## Troubleshooting

### Common Issues

1. **Empty Search Results**
   - Check similarity threshold (currently 0.3)
   - Verify collection name includes prefix
   - Ensure documents are properly chunked

2. **Broken Pipe Errors**
   - Typically caused by long-running queries
   - Increase timeout values if needed
   - Monitor `/home/ken/ai/dominus-ai/logs/bridge.log`

3. **Collection Not Found**
   - Collections use 'dominus_' prefix
   - Use full name or clean name in API calls
   - Check with /collections endpoint

## Future Enhancements

### Phase 3B-3D (Planned)
- **3B**: Advanced memory patterns and long-term storage
- **3C**: Multi-agent collaboration system
- **3D**: Tool use and function calling

### Immediate Improvements
- Add PDF and image document support
- Implement collection management UI
- Add document update/delete capabilities
- Enhance chunking strategies for code

## Conclusion

The RAG system is fully operational and integrated into the Dominus AI infrastructure. It provides:
- ✓ Semantic search across 145+ document chunks
- ✓ Context-aware responses with document retrieval
- ✓ Session persistence and conversation history
- ✓ Full integration with Darkfoo terminal
- ✓ Production deployment with HTTPS access

The system successfully enhances the AI's capabilities by grounding responses in actual project documentation and code, providing more accurate and contextual assistance.