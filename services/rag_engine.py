#!/usr/bin/env python3
"""
RAG (Retrieval Augmented Generation) Engine for Dominus AI
Provides semantic search and document retrieval capabilities
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import pickle

# ChromaDB for vector storage
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

# Document processing
from dataclasses import dataclass
import tiktoken

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a document in the RAG system"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    chunk_id: Optional[int] = None
    

class RAGEngine:
    """
    Core RAG engine for document retrieval and augmentation
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize RAG engine with configuration"""
        self.config = config or self._default_config()
        
        # Initialize ChromaDB client
        self.client = self._init_chromadb()
        
        # Initialize embedding function
        self.embedding_function = self._init_embeddings()
        
        # Token counter for chunk sizing
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Cache for embeddings
        self.embedding_cache = {}
        self.cache_file = Path(self.config['cache_dir']) / 'embedding_cache.pkl'
        self._load_cache()
        
        logger.info("RAG Engine initialized successfully")
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'persist_dir': '/home/ken/ai/dominus-ai/data/chromadb',
            'cache_dir': '/home/ken/ai/dominus-ai/data/cache',
            'embedding_model': 'all-MiniLM-L6-v2',
            'chunk_size': 512,
            'chunk_overlap': 50,
            'max_results': 5,
            'similarity_threshold': 0.3,  # Lowered for better recall
            'collection_prefix': 'dominus_'
        }
    
    def _init_chromadb(self) -> chromadb.Client:
        """Initialize ChromaDB client with persistence"""
        persist_dir = Path(self.config['persist_dir'])
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Use new ChromaDB API
        client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        logger.info(f"ChromaDB initialized with persist_dir: {persist_dir}")
        return client
    
    def _init_embeddings(self):
        """Initialize embedding function"""
        # Use ChromaDB's built-in sentence transformers
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.config['embedding_model']
        )
    
    def _load_cache(self):
        """Load embedding cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    self.embedding_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.embedding_cache)} cached embeddings")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self.embedding_cache = {}
    
    def _save_cache(self):
        """Save embedding cache to disk"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.embedding_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
    
    def create_collection(self, name: str, metadata: Optional[Dict] = None) -> chromadb.Collection:
        """Create or get a collection"""
        collection_name = f"{self.config['collection_prefix']}{name}"
        
        # Ensure metadata is not empty
        collection_metadata = metadata or {'type': 'document', 'created': datetime.now().isoformat()}
        
        try:
            collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                metadata=collection_metadata
            )
            logger.info(f"Created collection: {collection_name}")
        except Exception as e:
            # Collection already exists or other error
            if "already exists" in str(e).lower():
                collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self.embedding_function
                )
                logger.info(f"Retrieved existing collection: {collection_name}")
            else:
                raise e
        
        return collection
    
    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Document]:
        """
        Split text into chunks with overlap
        """
        tokens = self.tokenizer.encode(text)
        chunk_size = self.config['chunk_size']
        overlap = self.config['chunk_overlap']
        
        chunks = []
        doc_id = hashlib.md5(text.encode()).hexdigest()[:16]
        
        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            chunk_metadata = {
                'doc_id': doc_id,
                'chunk_id': len(chunks),
                'chunk_start': i,
                'chunk_end': min(i + chunk_size, len(tokens)),
                'timestamp': datetime.now().isoformat()
            }
            
            if metadata:
                chunk_metadata.update(metadata)
            
            chunks.append(Document(
                id=f"{doc_id}_{len(chunks)}",
                content=chunk_text,
                metadata=chunk_metadata,
                chunk_id=len(chunks)
            ))
        
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks
    
    def ingest_document(self, 
                       collection_name: str,
                       content: str,
                       metadata: Optional[Dict] = None,
                       doc_id: Optional[str] = None) -> List[str]:
        """
        Ingest a document into the vector database
        """
        collection = self.create_collection(collection_name)
        
        # Chunk the document
        chunks = self.chunk_text(content, metadata)
        
        # Prepare data for ChromaDB
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        
        # Add to collection
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        logger.info(f"Ingested {len(chunks)} chunks into {collection_name}")
        return ids
    
    def search(self,
               collection_name: str,
               query: str,
               k: Optional[int] = None,
               filters: Optional[Dict] = None) -> List[Dict]:
        """
        Search for relevant documents
        """
        try:
            collection = self.client.get_collection(
                name=f"{self.config['collection_prefix']}{collection_name}",
                embedding_function=self.embedding_function
            )
        except ValueError:
            logger.warning(f"Collection {collection_name} not found")
            return []
        
        k = k or self.config['max_results']
        
        # Perform search
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where=filters
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        # Filter by similarity threshold if distances are available
        if 'distances' in results:
            threshold = self.config['similarity_threshold']
            formatted_results = [
                r for r in formatted_results 
                if r['distance'] is None or (1 - r['distance']) >= threshold
            ]
        
        logger.info(f"Found {len(formatted_results)} results for query")
        return formatted_results
    
    def augment_prompt(self, 
                      query: str,
                      documents: List[Dict],
                      max_context_length: int = 2000) -> str:
        """
        Augment a prompt with retrieved documents
        """
        if not documents:
            return query
        
        # Build context from documents
        context_parts = []
        total_length = 0
        
        for i, doc in enumerate(documents, 1):
            doc_text = f"[Document {i}]:\n{doc['content']}\n"
            doc_length = len(self.tokenizer.encode(doc_text))
            
            if total_length + doc_length > max_context_length:
                break
                
            context_parts.append(doc_text)
            total_length += doc_length
        
        context = "\n".join(context_parts)
        
        # Create augmented prompt
        augmented = f"""Based on the following context, answer the question.
If the answer cannot be found in the context, say so.

Context:
{context}

Question: {query}

Answer:"""
        
        return augmented
    
    def list_collections(self) -> List[Dict]:
        """List all collections"""
        collections = []
        for col in self.client.list_collections():
            if col.name.startswith(self.config['collection_prefix']):
                clean_name = col.name[len(self.config['collection_prefix']):]
                collections.append({
                    'name': clean_name,
                    'full_name': col.name,
                    'count': col.count() if hasattr(col, 'count') else 'unknown'
                })
        return collections
    
    def delete_collection(self, name: str) -> bool:
        """Delete a collection"""
        collection_name = f"{self.config['collection_prefix']}{name}"
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get RAG engine statistics"""
        collections = self.list_collections()
        
        stats = {
            'collections': len(collections),
            'collection_details': collections,
            'cache_size': len(self.embedding_cache),
            'config': self.config
        }
        
        return stats


# Singleton instance
_rag_engine = None

def get_rag_engine(config: Optional[Dict] = None) -> RAGEngine:
    """Get or create RAG engine instance"""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine(config)
    return _rag_engine


if __name__ == "__main__":
    # Test the RAG engine
    engine = get_rag_engine()
    
    # Test document ingestion
    test_doc = """
    Dominus AI is an advanced artificial intelligence platform that provides
    context-aware conversations, document retrieval, and knowledge management.
    It uses ChromaDB for vector storage and supports multiple document formats.
    """
    
    # Ingest test document
    doc_ids = engine.ingest_document(
        collection_name="test",
        content=test_doc,
        metadata={'type': 'test', 'source': 'manual'}
    )
    
    print(f"Ingested document chunks: {doc_ids}")
    
    # Test search
    results = engine.search(
        collection_name="test",
        query="What is Dominus AI?"
    )
    
    print(f"\nSearch results: {len(results)} found")
    for result in results:
        print(f"- {result['id']}: {result['content'][:100]}...")
    
    # Show stats
    stats = engine.get_stats()
    print(f"\nRAG Engine Stats:")
    print(json.dumps(stats, indent=2))