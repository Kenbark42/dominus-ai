#!/usr/bin/env python3
"""
Context-Aware Bridge for Dominus AI
Extends the basic bridge with conversation memory and context management
"""

import http.server
import json
import urllib.request
import socketserver
import sys
import time
import threading
from io import BytesIO
from http.server import BaseHTTPRequestHandler
from typing import Dict, Optional, Any

# Import context manager
from context_manager import get_context_manager, Message

# Import RAG engine
try:
    from rag_engine import get_rag_engine
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    print("[Bridge] RAG engine not available - some features disabled")


class ContextAwareBridge(BaseHTTPRequestHandler):
    """HTTP handler with context management capabilities"""
    
    # Class-level context manager (shared across requests)
    context_manager = None
    
    @classmethod
    def initialize_context_manager(cls, config: Optional[Dict] = None):
        """Initialize the context manager"""
        if cls.context_manager is None:
            cls.context_manager = get_context_manager(config)
            # Start cleanup thread
            cleanup_thread = threading.Thread(target=cls._cleanup_worker, daemon=True)
            cleanup_thread.start()
    
    @classmethod
    def _cleanup_worker(cls):
        """Background thread for session cleanup"""
        while True:
            time.sleep(3600)  # Run every hour
            try:
                cls.context_manager.cleanup_old_sessions()
            except Exception as e:
                print(f"[Bridge] Cleanup error: {e}")
    
    def do_POST(self):
        """Handle POST requests with context awareness"""
        
        # Handle different endpoints
        if self.path == '/chat':
            self.handle_chat()
        elif self.path == '/chat/rag':
            self.handle_rag_chat()
        elif self.path == '/generate':
            # Legacy endpoint - convert to chat format
            self.handle_legacy_generate()
        elif self.path == '/session/create':
            self.handle_session_create()
        elif self.path == '/session/info':
            self.handle_session_info()
        elif self.path == '/ingest':
            self.handle_document_ingest()
        elif self.path == '/search':
            self.handle_search()
        elif self.path == '/collections':
            self.handle_collections()
        elif self.path == '/health':
            self.handle_health()
        else:
            self.send_error(404, "Endpoint not found")
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self.handle_health()
        elif self.path == '/collections':
            self.handle_collections()
        else:
            self.send_error(404, "Endpoint not found")
    
    def handle_chat(self):
        """Handle context-aware chat endpoint"""
        try:
            # Parse request
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters
            session_id = data.get('session_id')
            message = data.get('message', data.get('inputs', ''))
            params = data.get('parameters', {})
            context_options = data.get('context_options', {})
            
            if not message:
                self.send_json_response(400, {'error': 'Message is required'})
                return
            
            # Get or create session
            session_id = self.context_manager.get_or_create_session(session_id)
            
            # Add user message to history
            self.context_manager.add_message(session_id, 'user', message)
            
            # Build prompt with context
            system_prompt = context_options.get('system_prompt')
            
            # Get context tokens if available (for efficiency)
            context_tokens = None
            if context_options.get('use_context_tokens', True):
                context_tokens = self.context_manager.get_context_tokens(session_id)
            
            # Prepare Ollama request
            if context_tokens:
                # Use existing context tokens for continuation
                ollama_request = self._build_continuation_request(
                    message, context_tokens, params
                )
            else:
                # Build full prompt with history
                full_prompt = self.context_manager.build_prompt_with_context(
                    session_id, message, system_prompt
                )
                ollama_request = self._build_initial_request(
                    full_prompt, params
                )
            
            # Call Ollama
            start_time = time.time()
            response_data = self._call_ollama(ollama_request)
            elapsed = time.time() - start_time
            
            if not response_data:
                self.send_json_response(500, {'error': 'Failed to get response from Ollama'})
                return
            
            # Extract response
            response_text = response_data.get('response', '')
            thinking_text = response_data.get('thinking', '')
            new_context_tokens = response_data.get('context', [])
            
            # Handle empty response with thinking
            if not response_text and thinking_text:
                response_text = "I understand your request. Let me help you with that."
            
            # Add assistant response to history
            assistant_msg = self.context_manager.add_message(
                session_id, 'assistant', response_text
            )
            
            # Update context tokens for next request
            if new_context_tokens:
                self.context_manager.update_context_tokens(session_id, new_context_tokens)
            
            # Prepare response
            result = {
                'response': response_text,
                'session_id': session_id,
                'message_id': assistant_msg.message_id,
                'thinking': thinking_text if context_options.get('include_thinking', False) else None,
                'usage': {
                    'prompt_tokens': response_data.get('prompt_eval_count', 0),
                    'completion_tokens': response_data.get('eval_count', 0),
                    'total_tokens': response_data.get('prompt_eval_count', 0) + 
                                   response_data.get('eval_count', 0),
                    'context_size': len(new_context_tokens),
                    'response_time': elapsed
                }
            }
            
            # Remove None values
            result = {k: v for k, v in result.items() if v is not None}
            
            self.send_json_response(200, result)
            
        except Exception as e:
            print(f"[Bridge] Error in handle_chat: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {'error': str(e)})
    
    def handle_legacy_generate(self):
        """Handle legacy /generate endpoint without context"""
        try:
            # Parse request
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters
            prompt = data.get('inputs', '')
            params = data.get('parameters', {})
            
            if not prompt:
                self.send_json_response(400, {'error': 'inputs field is required'})
                return
            
            # Build Ollama request
            max_tokens = params.get('max_new_tokens', 2048)  # Increased from 500
            if max_tokens < 100:
                max_tokens = 100  # Minimum to avoid empty responses
                
            ollama_request = {
                'model': 'gpt-oss:120b',
                'prompt': prompt,
                'stream': False,
                'options': {
                    'num_predict': max_tokens,
                    'temperature': params.get('temperature', 0.7),
                    'top_p': params.get('top_p', 0.95),
                    'repeat_penalty': params.get('repetition_penalty', 1.1),
                    'stop': params.get('stop_sequences', [])
                }
            }
            
            # Call Ollama directly (no context for legacy endpoint)
            result = self._call_ollama(ollama_request)
            
            if result and 'response' in result:
                response_text = result['response']
                # Handle empty response or thinking-only response
                if not response_text or response_text.strip() == '' or 'thinking>' in response_text and len(response_text) < 100:
                    response_text = "I understand your query. Could you please provide more context or rephrase your question?"
            else:
                response_text = "Sorry, I couldn't generate a response. Please try again."
            
            # Send response in TGI format
            self.send_json_response(200, {
                'generated_text': response_text
            })
            
        except json.JSONDecodeError as e:
            print(f"[Bridge] JSON decode error: {e}")
            print(f"[Bridge] Raw data: {post_data[:100] if 'post_data' in locals() else 'N/A'}")
            self.send_json_response(400, {'error': f'Invalid JSON: {str(e)}'})
        except Exception as e:
            print(f"[Bridge] Error in legacy handler: {e}")
            import traceback
            traceback.print_exc()
            self.send_json_response(500, {'error': str(e)})
    
    def handle_session_create(self):
        """Create a new session explicitly"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            metadata = {}
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                metadata = data.get('metadata', {})
            
            session_id = self.context_manager.create_session(metadata)
            
            self.send_json_response(200, {
                'session_id': session_id,
                'created': True
            })
            
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})
    
    def handle_session_info(self):
        """Get session information"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            session_id = data.get('session_id')
            if not session_id:
                self.send_json_response(400, {'error': 'session_id required'})
                return
            
            info = self.context_manager.get_session_info(session_id)
            if not info:
                self.send_json_response(404, {'error': 'Session not found'})
                return
            
            self.send_json_response(200, info)
            
        except Exception as e:
            self.send_json_response(500, {'error': str(e)})
    
    def handle_health(self):
        """Health check endpoint"""
        try:
            # Check Ollama
            req = urllib.request.Request('http://localhost:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as response:
                models = json.loads(response.read().decode('utf-8'))
                has_model = any(m['name'] == 'gpt-oss:120b' for m in models.get('models', []))
            
            # Get context manager stats
            active_sessions = len(self.context_manager.conversations) if self.context_manager else 0
            
            self.send_json_response(200, {
                'status': 'ok',
                'ollama': 'connected',
                'model': 'gpt-oss:120b' if has_model else 'not found',
                'context_manager': 'active',
                'active_sessions': active_sessions
            })
            
        except Exception as e:
            self.send_json_response(503, {
                'status': 'error',
                'error': str(e)
            })
    
    def _build_initial_request(self, prompt: str, params: Dict) -> Dict:
        """Build initial Ollama request"""
        max_tokens = params.get('max_new_tokens', 500)
        if max_tokens < 100:
            max_tokens = 100
            
        return {
            'model': 'gpt-oss:120b',
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': params.get('temperature', 0.7),
                'top_p': params.get('top_p', 0.95),
                'top_k': params.get('top_k', 40),
                'num_predict': max_tokens,
                'num_ctx': 32768,  # Increased from 8192
                'repeat_penalty': params.get('repetition_penalty', 1.1),
                'stop': params.get('stop_sequences', []),
            }
        }
    
    def _build_continuation_request(self, prompt: str, context: list, params: Dict) -> Dict:
        """Build continuation request with existing context"""
        max_tokens = params.get('max_new_tokens', 500)
        if max_tokens < 100:
            max_tokens = 100
            
        return {
            'model': 'gpt-oss:120b',
            'prompt': f"User: {prompt}\nAssistant:",
            'context': context,  # Reuse context tokens
            'stream': False,
            'options': {
                'temperature': params.get('temperature', 0.7),
                'top_p': params.get('top_p', 0.95),
                'top_k': params.get('top_k', 40),
                'num_predict': max_tokens,
                'num_ctx': 32768,  # Increased from 8192
                'repeat_penalty': params.get('repetition_penalty', 1.1),
                'stop': params.get('stop_sequences', []),
            }
        }
    
    def _call_ollama(self, request_data: Dict) -> Optional[Dict]:
        """Call Ollama API"""
        try:
            req = urllib.request.Request(
                'http://localhost:11434/api/generate',
                data=json.dumps(request_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=600) as response:  # Increased timeout
                return json.loads(response.read().decode('utf-8'))
                
        except Exception as e:
            print(f"[Bridge] Ollama call error: {e}")
            return None
    
    def handle_rag_chat(self):
        """Handle RAG-enhanced chat endpoint"""
        if not RAG_AVAILABLE:
            self.send_json_response(503, {'error': 'RAG engine not available'})
            return
            
        try:
            # Parse request
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Extract parameters
            session_id = data.get('session_id')
            message = data.get('message', '')
            params = data.get('parameters', {})
            collection = data.get('collection', 'default')
            use_rag = data.get('use_rag', True)
            
            if not message:
                self.send_json_response(400, {'error': 'Message is required'})
                return
            
            # Get or create session
            session_id = self.context_manager.get_or_create_session(session_id)
            
            # Search for relevant documents if RAG is enabled
            augmented_prompt = message
            retrieved_docs = []
            
            if use_rag:
                rag_engine = get_rag_engine()
                # Search for relevant documents
                retrieved_docs = rag_engine.search(
                    collection_name=collection,
                    query=message,
                    k=params.get('rag_k', 3)
                )
                
                # Augment prompt with retrieved documents
                if retrieved_docs:
                    augmented_prompt = rag_engine.augment_prompt(message, retrieved_docs)
            
            # Add user message to history
            self.context_manager.add_message(session_id, 'user', message)
            
            # Build context from history and RAG
            context = self.context_manager.get_context(session_id, max_tokens=4000)
            full_prompt = f"{context}\n\nUser: {augmented_prompt}\nAssistant:"
            
            # Call Ollama
            request_data = self._build_initial_request(full_prompt, params)
            response_data = self._call_ollama(request_data)
            
            if response_data and 'response' in response_data:
                response_text = response_data['response']
                
                # Add assistant response to history
                self.context_manager.add_message(session_id, 'assistant', response_text)
                
                result = {
                    'response': response_text,
                    'session_id': session_id,
                    'message_id': None,
                    'retrieved_documents': len(retrieved_docs),
                    'usage': {
                        'prompt_tokens': response_data.get('prompt_eval_count', 0),
                        'completion_tokens': response_data.get('eval_count', 0),
                        'total_tokens': response_data.get('prompt_eval_count', 0) + response_data.get('eval_count', 0),
                        'response_time': response_data.get('total_duration', 0) / 1e9
                    }
                }
                
                self.send_json_response(200, result)
            else:
                self.send_json_response(500, {'error': 'Failed to generate response'})
                
        except Exception as e:
            print(f"[Bridge] Error in RAG chat: {e}")
            self.send_json_response(500, {'error': str(e)})
    
    def handle_document_ingest(self):
        """Handle document ingestion endpoint"""
        if not RAG_AVAILABLE:
            self.send_json_response(503, {'error': 'RAG engine not available'})
            return
            
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            collection = data.get('collection', 'default')
            content = data.get('content', '')
            metadata = data.get('metadata', {})
            
            if not content:
                self.send_json_response(400, {'error': 'Content is required'})
                return
            
            rag_engine = get_rag_engine()
            doc_ids = rag_engine.ingest_document(
                collection_name=collection,
                content=content,
                metadata=metadata
            )
            
            self.send_json_response(200, {
                'success': True,
                'document_chunks': len(doc_ids),
                'chunk_ids': doc_ids
            })
            
        except Exception as e:
            print(f"[Bridge] Error in document ingest: {e}")
            self.send_json_response(500, {'error': str(e)})
    
    def handle_search(self):
        """Handle semantic search endpoint"""
        if not RAG_AVAILABLE:
            self.send_json_response(503, {'error': 'RAG engine not available'})
            return
            
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            query = data.get('query', '')
            collection = data.get('collection', 'default')
            k = data.get('k', 5)
            
            if not query:
                self.send_json_response(400, {'error': 'Query is required'})
                return
            
            rag_engine = get_rag_engine()
            results = rag_engine.search(
                collection_name=collection,
                query=query,
                k=k
            )
            
            self.send_json_response(200, {
                'query': query,
                'results': results,
                'count': len(results)
            })
            
        except Exception as e:
            print(f"[Bridge] Error in search: {e}")
            self.send_json_response(500, {'error': str(e)})
    
    def handle_collections(self):
        """Handle collections listing endpoint"""
        if not RAG_AVAILABLE:
            self.send_json_response(503, {'error': 'RAG engine not available'})
            return
            
        try:
            rag_engine = get_rag_engine()
            collections = rag_engine.list_collections()
            
            self.send_json_response(200, {
                'collections': collections,
                'count': len(collections)
            })
            
        except Exception as e:
            print(f"[Bridge] Error listing collections: {e}")
            self.send_json_response(500, {'error': str(e)})
    
    def send_json_response(self, status: int, data: Any):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Log to stdout"""
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()


# Fix for BytesIO import
from io import BytesIO


def main():
    """Main entry point"""
    PORT = 8090  # Primary bridge port
    
    # Configuration
    config = {
        'max_context_tokens': 6000,
        'max_messages': 50,
        'session_ttl': 86400,
        'db_path': '/home/ken/ai/dominus-ai/data/conversations.db'
    }
    
    # Initialize context manager
    ContextAwareBridge.initialize_context_manager(config)
    
    # Start server
    socketserver.TCPServer.allow_reuse_address = True
    
    print(f"Starting Context-Aware Bridge on port {PORT}")
    print(f"Endpoints:")
    print(f"  POST /chat           - Context-aware chat")
    print(f"  POST /chat/rag       - RAG-enhanced chat")
    print(f"  POST /generate       - Legacy endpoint (limited context)")
    print(f"  POST /session/create - Create new session")
    print(f"  POST /session/info   - Get session information")
    print(f"  POST /ingest         - Ingest document into RAG")
    print(f"  POST /search         - Semantic search")
    print(f"  GET  /collections    - List document collections")
    print(f"  GET  /health         - Health check")
    
    if RAG_AVAILABLE:
        print(f"\n✓ RAG Engine: Available")
    else:
        print(f"\n✗ RAG Engine: Not available (install chromadb)")
    
    with socketserver.TCPServer(("", PORT), ContextAwareBridge) as httpd:
        print(f"Bridge ready - Listening on port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            httpd.shutdown()


if __name__ == '__main__':
    main()