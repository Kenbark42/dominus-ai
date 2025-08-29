# Dominus AI - Context & Conversation Management Architecture

## Overview

A robust context management system that maintains conversation history across requests, enabling coherent multi-turn dialogues with memory persistence.

## Current Limitations

1. **Stateless Requests**: Each API call is independent with no memory
2. **No User Tracking**: Cannot differentiate between users/sessions
3. **No Persistence**: Conversations lost on service restart
4. **No Context Window Management**: No handling of token limits

## Proposed Architecture

```
┌─────────────────────────────────────────────────┐
│                   Client Layer                   │
├─────────────────────────────────────────────────┤
│         Session ID / User ID / API Key           │
└────────────────────┬─────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   API Gateway (8090)    │
        │  - Session Management   │
        │  - Request Routing      │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │  Context Manager Service │
        │  - History Retrieval     │
        │  - Context Assembly      │
        │  - Token Management      │
        └────────────┬────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼────┐    ┌────▼────┐    ┌────▼────┐
│ Memory  │    │ Vector  │    │  Cache  │
│  Store  │    │   DB    │    │ (Redis) │
└─────────┘    └─────────┘    └─────────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
        ┌────────────▼────────────┐
        │   Ollama API (11434)    │
        │  - Context Injection    │
        │  - Response Generation  │
        └──────────────────────────┘
```

## Core Components

### 1. Session Management
- **Session ID Generation**: UUID-based unique identifiers
- **User Authentication**: Optional API key system
- **Session Metadata**: Timestamps, token counts, model preferences

### 2. Context Manager
```python
class ContextManager:
    - manage_conversation_history()
    - build_context_window()
    - prune_old_messages()
    - calculate_token_usage()
    - handle_context_overflow()
```

### 3. Storage Layers

#### Short-term Memory (Redis)
- Active conversations (last 24 hours)
- Quick access to recent context
- Session state caching

#### Long-term Memory (PostgreSQL/SQLite)
- Conversation archives
- User preferences
- Analytics data

#### Vector Database (ChromaDB/Pinecone)
- Semantic search across conversations
- RAG (Retrieval Augmented Generation)
- Knowledge base integration

### 4. Context Window Management

```python
class ContextWindow:
    max_tokens: 8192
    reserve_tokens: 1000  # For response
    
    strategies:
        - sliding_window: Keep last N messages
        - importance_scoring: Prioritize key messages
        - summarization: Compress old messages
        - hybrid: Combination of above
```

## Implementation Phases

### Phase 1: Basic Context (Week 1)
- Session ID tracking
- In-memory conversation storage
- Simple sliding window context
- RESTful API endpoints

### Phase 2: Persistence (Week 2)
- Redis integration for caching
- SQLite for conversation storage
- Session recovery after restart
- Basic analytics

### Phase 3: Advanced Features (Week 3-4)
- Vector database for semantic search
- RAG implementation
- Multi-user support
- Context summarization
- Tool memory integration

## API Changes

### Current API
```json
POST /generate
{
    "inputs": "Hello",
    "parameters": {...}
}
```

### Enhanced API
```json
POST /chat
{
    "session_id": "uuid-1234",
    "message": "Hello",
    "parameters": {
        "max_tokens": 500,
        "temperature": 0.7
    },
    "context_options": {
        "max_history": 10,
        "include_summary": true,
        "use_rag": false
    }
}

Response:
{
    "response": "Hello! How can I help?",
    "session_id": "uuid-1234",
    "message_id": "msg-5678",
    "token_usage": {
        "prompt": 150,
        "completion": 50,
        "total": 200,
        "context_remaining": 7992
    }
}
```

## Storage Schema

### Conversations Table
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    model VARCHAR(100),
    metadata JSONB
);
```

### Messages Table
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20), -- 'user', 'assistant', 'system'
    content TEXT,
    tokens INTEGER,
    timestamp TIMESTAMP,
    metadata JSONB
);
```

### Context Cache (Redis)
```
Key: session:{session_id}:context
Value: JSON array of recent messages
TTL: 86400 (24 hours)

Key: session:{session_id}:tokens
Value: Context token array from Ollama
TTL: 3600 (1 hour)
```

## Benefits

1. **Coherent Conversations**: Maintains context across multiple interactions
2. **User Personalization**: Remember preferences and history per user
3. **Efficiency**: Reuse context tokens from Ollama
4. **Scalability**: Distributed caching and storage
5. **Analytics**: Track usage patterns and optimize
6. **Recovery**: Conversations survive restarts

## Technical Requirements

### Dependencies
```python
# Core
redis>=5.0.0
sqlalchemy>=2.0.0
asyncio
aiohttp

# Optional (Phase 3)
chromadb>=0.4.0
langchain>=0.1.0
sentence-transformers>=2.0.0
```

### System Requirements
- Redis server (for caching)
- PostgreSQL or SQLite (for persistence)
- Additional 2-4GB RAM for vector DB (optional)
- SSD storage recommended for database

## Security Considerations

1. **Session Security**: 
   - Secure session ID generation
   - Session expiration policies
   - Rate limiting per session

2. **Data Privacy**:
   - Encryption at rest for stored conversations
   - Optional conversation deletion
   - GDPR compliance features

3. **Access Control**:
   - API key authentication
   - Role-based access (future)
   - Audit logging

## Performance Metrics

- Session creation: < 10ms
- Context retrieval: < 50ms
- Full request with context: < 100ms overhead
- Storage: ~1KB per message average
- Cache hit rate target: > 90%

## Migration Path

1. Deploy new context-aware bridge alongside existing
2. Gradual migration of clients to new endpoints
3. Backwards compatibility mode for legacy requests
4. Full cutover after validation period

## Monitoring & Observability

- Session count metrics
- Context size distribution
- Token usage analytics
- Cache hit/miss rates
- Storage growth trends
- Response time histograms

This architecture provides a solid foundation for context management while remaining flexible for future enhancements.