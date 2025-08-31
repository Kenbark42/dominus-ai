# Phase 3: RAG (Retrieval Augmented Generation) System
## Dominus AI - Advanced Knowledge Integration

### Overview
The RAG system will extend Dominus AI with the ability to reference, search, and utilize external documents and code repositories to provide grounded, accurate responses with citations.

### Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Dominus AI Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Context    │  │     RAG      │  │   Future     │      │
│  │   Manager    │◄─┤    Engine    ├─►│   Agents     │      │
│  │  (Phase 2)   │  │  (Phase 3A)  │  │  (Phase 3B)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         ▲                 │                   │              │
│         │                 ▼                   │              │
│  ┌──────────────────────────────────────────────┐           │
│  │           Plugin Architecture Layer           │           │
│  └──────────────────────────────────────────────┘           │
│         │                 │                   │              │
│         ▼                 ▼                   ▼              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Vector     │  │   Document   │  │  Knowledge   │      │
│  │   Database   │  │   Ingestion  │  │    Graph     │      │
│  │  (ChromaDB)  │  │   Pipeline   │  │   (Future)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Component Design

#### 1. Vector Database Layer
**Technology**: ChromaDB (with potential migration path to Qdrant)
- **Local deployment** for privacy and speed
- **Persistent storage** in SQLite/DuckDB backend
- **Collections** for different document types:
  - `code_repository` - Source code files
  - `documentation` - Markdown, PDFs, text
  - `conversations` - Historical chat contexts
  - `web_content` - Scraped/fetched web pages

#### 2. Document Ingestion Pipeline
```python
class DocumentIngestionPipeline:
    """
    Modular pipeline for processing various document types
    """
    
    supported_formats = {
        'code': ['.py', '.js', '.ts', '.go', '.rs', '.cpp'],
        'docs': ['.md', '.txt', '.pdf', '.html'],
        'data': ['.json', '.yaml', '.csv', '.xml']
    }
    
    processors = {
        'code': CodeProcessor(),      # AST parsing, dependency extraction
        'docs': DocumentProcessor(),   # Text extraction, formatting
        'data': DataProcessor()        # Structured data parsing
    }
    
    def ingest(self, path, metadata=None):
        # Process based on file type
        # Extract text and metadata
        # Generate embeddings
        # Store in vector DB
```

#### 3. Embedding Service
```python
class EmbeddingService:
    """
    Handles text-to-vector conversion
    """
    
    models = {
        'default': 'sentence-transformers/all-MiniLM-L6-v2',
        'code': 'microsoft/codebert-base',
        'multilingual': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    }
    
    def embed_text(self, text, model='default'):
        # Generate embeddings
        # Cache frequently used embeddings
        # Return vector representation
```

#### 4. RAG Engine
```python
class RAGEngine:
    """
    Core retrieval and augmentation engine
    """
    
    def __init__(self):
        self.vector_db = ChromaDBClient()
        self.embedding_service = EmbeddingService()
        self.reranker = ReRanker()  # Optional: for result quality
        
    async def retrieve(self, query, k=5, filters=None):
        # Embed query
        # Search vector DB
        # Re-rank results
        # Return relevant documents
        
    async def augment_prompt(self, query, context, documents):
        # Combine query with retrieved documents
        # Format for LLM consumption
        # Include citations
```

### Integration Points

#### 1. Context Manager Integration
```python
# Extend existing context_manager.py
class EnhancedContextManager(ContextManager):
    def __init__(self):
        super().__init__()
        self.rag_engine = RAGEngine()
        
    async def get_augmented_context(self, session_id, query):
        # Get conversation context
        context = self.get_context(session_id)
        
        # Retrieve relevant documents
        documents = await self.rag_engine.retrieve(query)
        
        # Combine context with RAG results
        return self.format_augmented_context(context, documents)
```

#### 2. API Endpoints
```python
# New endpoints in context_bridge.py
POST /ingest       - Upload documents for indexing
POST /search       - Semantic search across documents
POST /chat/rag     - RAG-enhanced chat endpoint
GET  /collections  - List available document collections
DELETE /document   - Remove document from index
```

### Implementation Phases

#### Phase 3A.1: Foundation (Week 1)
- [ ] Set up ChromaDB with persistent storage
- [ ] Create basic document ingestion for text/markdown
- [ ] Implement embedding service with caching
- [ ] Basic semantic search functionality

#### Phase 3A.2: Integration (Week 2)
- [ ] Integrate RAG with existing context system
- [ ] Add citation tracking and formatting
- [ ] Implement document management API
- [ ] Create web UI for document upload

#### Phase 3A.3: Enhancement (Week 3)
- [ ] Add code file processing with AST parsing
- [ ] Implement PDF ingestion
- [ ] Add re-ranking for better results
- [ ] Performance optimization and caching

#### Phase 3A.4: Advanced Features (Week 4)
- [ ] Hybrid search (keyword + semantic)
- [ ] Document update detection and re-indexing
- [ ] Query expansion and optimization
- [ ] Evaluation metrics and tuning

### Future Extensibility

#### Plugin Architecture
```python
class DominusPlugin:
    """Base class for future extensions"""
    
    @abstractmethod
    def initialize(self, config):
        pass
        
    @abstractmethod
    def process(self, input_data):
        pass
        
    @abstractmethod
    def get_capabilities(self):
        pass

# Future plugins
class MultiAgentPlugin(DominusPlugin):
    """Phase 3B: Multi-agent coordination"""
    
class KnowledgeGraphPlugin(DominusPlugin):
    """Phase 3D: Knowledge graph integration"""
    
class CodeIntelligencePlugin(DominusPlugin):
    """Phase 3C: Code analysis and generation"""
```

### Technical Stack

#### Required Dependencies
```python
# requirements.txt additions
chromadb==0.4.22
sentence-transformers==2.2.2
pypdf==4.0.0
beautifulsoup4==4.12.3
lxml==5.0.0
tiktoken==0.5.2
langchain-community==0.0.10  # Optional, for utilities
```

#### System Requirements
- **Storage**: ~10GB for vector database (scales with documents)
- **RAM**: Additional 2-4GB for embedding models
- **CPU**: Embedding generation benefits from multiple cores
- **GPU**: Optional, speeds up embedding generation

### Configuration

```yaml
# config/rag_config.yaml
rag:
  vector_db:
    type: chromadb
    persist_directory: /home/ken/ai/dominus-ai/data/chromadb
    collection_prefix: dominus_
    
  embedding:
    model: sentence-transformers/all-MiniLM-L6-v2
    cache_size: 10000
    batch_size: 32
    
  retrieval:
    default_k: 5
    max_k: 20
    similarity_threshold: 0.7
    rerank: true
    
  ingestion:
    chunk_size: 512
    chunk_overlap: 50
    max_file_size: 100MB
    auto_index: true
```

### Security Considerations

1. **Document Access Control**
   - User-based collections
   - Permission checking before retrieval
   - Audit logging for sensitive documents

2. **Input Sanitization**
   - File type validation
   - Content scanning for malicious code
   - Size limits and rate limiting

3. **Data Privacy**
   - Local deployment option
   - Encryption at rest for sensitive collections
   - Configurable data retention policies

### Performance Optimization

1. **Caching Strategy**
   - Embedding cache for frequent queries
   - Result cache with TTL
   - Precomputed document summaries

2. **Indexing Optimization**
   - Incremental indexing for large documents
   - Background processing queue
   - Batch operations for efficiency

3. **Search Optimization**
   - Approximate nearest neighbor search
   - Parallel query processing
   - Query result streaming

### Monitoring and Metrics

```python
# Metrics to track
metrics = {
    'ingestion_rate': 'documents/second',
    'search_latency': 'p50, p95, p99',
    'retrieval_accuracy': 'MRR, nDCG',
    'cache_hit_rate': 'percentage',
    'storage_usage': 'GB',
    'active_collections': 'count'
}
```

### Next Steps

1. **Immediate Actions**
   - Install ChromaDB and test basic functionality
   - Create ingestion script for markdown files
   - Implement basic embedding service
   - Test semantic search with sample documents

2. **Integration Tasks**
   - Extend context_bridge.py with RAG endpoints
   - Update frontend to support document upload
   - Add RAG toggle to chat interface
   - Create document management UI

3. **Testing Strategy**
   - Unit tests for each component
   - Integration tests for RAG pipeline
   - Performance benchmarks
   - Accuracy evaluation on test queries

This architecture provides a solid foundation for RAG while maintaining flexibility for future enhancements like multi-agent systems, knowledge graphs, and code intelligence features.