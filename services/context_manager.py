#!/usr/bin/env python3
"""
Context Manager for Dominus AI
Handles conversation history, context windows, and session management
"""

import json
import uuid
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import deque
import os
import sqlite3
import threading

# Optional imports (will add fallbacks)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class Message:
    """Represents a single message in a conversation"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: float
    tokens: Optional[int] = None
    metadata: Optional[Dict] = None
    message_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(**data)


@dataclass
class Conversation:
    """Represents a conversation session"""
    session_id: str
    messages: List[Message]
    created_at: float
    updated_at: float
    total_tokens: int = 0
    metadata: Optional[Dict] = None
    context_tokens: Optional[List[int]] = None  # Ollama context array
    
    def add_message(self, role: str, content: str, tokens: Optional[int] = None):
        """Add a message to the conversation"""
        msg = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            tokens=tokens
        )
        self.messages.append(msg)
        self.updated_at = time.time()
        if tokens:
            self.total_tokens += tokens
        return msg
    
    def get_context_window(self, max_tokens: int = 6000) -> List[Message]:
        """Get messages that fit within the token limit"""
        # Simple sliding window for now
        # TODO: Implement token counting
        result = []
        token_count = 0
        
        # Iterate from newest to oldest
        for msg in reversed(self.messages):
            msg_tokens = msg.tokens or len(msg.content.split()) * 1.3  # Rough estimate
            if token_count + msg_tokens > max_tokens:
                break
            result.insert(0, msg)
            token_count += msg_tokens
        
        return result
    
    def to_dict(self) -> Dict:
        return {
            'session_id': self.session_id,
            'messages': [m.to_dict() for m in self.messages],
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'total_tokens': self.total_tokens,
            'metadata': self.metadata,
            'context_tokens': self.context_tokens
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        data['messages'] = [Message.from_dict(m) for m in data.get('messages', [])]
        return cls(**data)


class ContextManager:
    """Main context management system"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Configuration
        self.max_context_tokens = self.config.get('max_context_tokens', 6000)
        self.max_messages = self.config.get('max_messages', 50)
        self.session_ttl = self.config.get('session_ttl', 86400)  # 24 hours
        self.db_path = self.config.get('db_path', '/home/ken/ai/dominus-ai/data/conversations.db')
        
        # In-memory storage
        self.conversations: Dict[str, Conversation] = {}
        self.lock = threading.RLock()
        
        # Initialize storage backends
        self._init_sqlite()
        self._init_redis()
        
        # Load active sessions
        self._load_active_sessions()
    
    def _init_sqlite(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        
        # Create tables
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        ''')
        
        self.db.execute('''
            CREATE INDEX IF NOT EXISTS idx_updated_at 
            ON conversations(updated_at)
        ''')
        
        self.db.commit()
    
    def _init_redis(self):
        """Initialize Redis connection if available"""
        self.redis = None
        if REDIS_AVAILABLE:
            try:
                self.redis = redis.Redis(
                    host=self.config.get('redis_host', 'localhost'),
                    port=self.config.get('redis_port', 6379),
                    db=self.config.get('redis_db', 0),
                    decode_responses=True
                )
                self.redis.ping()
                print("[ContextManager] Redis connected successfully")
            except Exception as e:
                print(f"[ContextManager] Redis not available: {e}")
                self.redis = None
    
    def _load_active_sessions(self):
        """Load recent sessions from database"""
        cutoff = time.time() - self.session_ttl
        cursor = self.db.execute(
            'SELECT session_id, data FROM conversations WHERE updated_at > ?',
            (cutoff,)
        )
        
        loaded = 0
        for row in cursor:
            try:
                conv = Conversation.from_dict(json.loads(row[1]))
                self.conversations[conv.session_id] = conv
                loaded += 1
            except Exception as e:
                print(f"[ContextManager] Error loading session {row[0]}: {e}")
        
        if loaded > 0:
            print(f"[ContextManager] Loaded {loaded} active sessions")
    
    def create_session(self, metadata: Optional[Dict] = None) -> str:
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        
        with self.lock:
            conv = Conversation(
                session_id=session_id,
                messages=[],
                created_at=time.time(),
                updated_at=time.time(),
                metadata=metadata or {}
            )
            
            self.conversations[session_id] = conv
            self._save_conversation(conv)
            
            # Cache in Redis if available
            if self.redis:
                try:
                    self.redis.setex(
                        f"session:{session_id}",
                        self.session_ttl,
                        json.dumps(conv.to_dict())
                    )
                except Exception as e:
                    print(f"[ContextManager] Redis cache error: {e}")
        
        return session_id
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """Get existing session or create new one"""
        if session_id and self.session_exists(session_id):
            return session_id
        return self.create_session()
    
    def session_exists(self, session_id: str) -> bool:
        """Check if session exists"""
        with self.lock:
            # Check memory
            if session_id in self.conversations:
                return True
            
            # Check Redis
            if self.redis:
                try:
                    if self.redis.exists(f"session:{session_id}"):
                        # Load from Redis to memory
                        data = self.redis.get(f"session:{session_id}")
                        conv = Conversation.from_dict(json.loads(data))
                        self.conversations[session_id] = conv
                        return True
                except Exception:
                    pass
            
            # Check database
            cursor = self.db.execute(
                'SELECT data FROM conversations WHERE session_id = ?',
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    conv = Conversation.from_dict(json.loads(row[0]))
                    self.conversations[session_id] = conv
                    return True
                except Exception:
                    pass
        
        return False
    
    def add_message(self, session_id: str, role: str, content: str, 
                   tokens: Optional[int] = None) -> Message:
        """Add a message to a conversation"""
        with self.lock:
            if session_id not in self.conversations:
                raise ValueError(f"Session {session_id} not found")
            
            conv = self.conversations[session_id]
            msg = conv.add_message(role, content, tokens)
            
            # Prune old messages if needed
            if len(conv.messages) > self.max_messages:
                conv.messages = conv.messages[-self.max_messages:]
            
            self._save_conversation(conv)
            
            return msg
    
    def get_context(self, session_id: str, max_tokens: Optional[int] = None) -> List[Message]:
        """Get conversation context for a session"""
        with self.lock:
            if session_id not in self.conversations:
                return []
            
            conv = self.conversations[session_id]
            max_tokens = max_tokens or self.max_context_tokens
            
            return conv.get_context_window(max_tokens)
    
    def update_context_tokens(self, session_id: str, context_tokens: List[int]):
        """Update Ollama context tokens for a session"""
        with self.lock:
            if session_id in self.conversations:
                conv = self.conversations[session_id]
                conv.context_tokens = context_tokens
                self._save_conversation(conv)
                
                # Cache in Redis for quick access
                if self.redis:
                    try:
                        self.redis.setex(
                            f"session:{session_id}:tokens",
                            3600,  # 1 hour TTL
                            json.dumps(context_tokens)
                        )
                    except Exception:
                        pass
    
    def get_context_tokens(self, session_id: str) -> Optional[List[int]]:
        """Get cached Ollama context tokens"""
        with self.lock:
            # Check memory
            if session_id in self.conversations:
                conv = self.conversations[session_id]
                if conv.context_tokens:
                    return conv.context_tokens
            
            # Check Redis
            if self.redis:
                try:
                    data = self.redis.get(f"session:{session_id}:tokens")
                    if data:
                        return json.loads(data)
                except Exception:
                    pass
            
            return None
    
    def build_prompt_with_context(self, session_id: str, user_message: str,
                                 system_prompt: Optional[str] = None) -> str:
        """Build a prompt with conversation context"""
        context = self.get_context(session_id)
        
        # Build the full prompt
        prompt_parts = []
        
        # Add system prompt if provided
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}\n")
        
        # Add conversation history
        for msg in context:
            if msg.role == 'user':
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == 'assistant':
                prompt_parts.append(f"Assistant: {msg.content}")
        
        # Add current message
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        
        return "\n\n".join(prompt_parts)
    
    def _save_conversation(self, conv: Conversation):
        """Save conversation to database"""
        try:
            data = json.dumps(conv.to_dict())
            self.db.execute(
                '''INSERT OR REPLACE INTO conversations 
                   (session_id, data, created_at, updated_at) 
                   VALUES (?, ?, ?, ?)''',
                (conv.session_id, data, conv.created_at, conv.updated_at)
            )
            self.db.commit()
        except Exception as e:
            print(f"[ContextManager] Error saving conversation: {e}")
    
    def cleanup_old_sessions(self):
        """Remove expired sessions"""
        cutoff = time.time() - self.session_ttl
        
        with self.lock:
            # Clean memory
            expired = [sid for sid, conv in self.conversations.items() 
                      if conv.updated_at < cutoff]
            for sid in expired:
                del self.conversations[sid]
            
            # Clean database
            self.db.execute('DELETE FROM conversations WHERE updated_at < ?', (cutoff,))
            self.db.commit()
            
            if expired:
                print(f"[ContextManager] Cleaned up {len(expired)} expired sessions")
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        with self.lock:
            if session_id not in self.conversations:
                return None
            
            conv = self.conversations[session_id]
            return {
                'session_id': session_id,
                'message_count': len(conv.messages),
                'total_tokens': conv.total_tokens,
                'created_at': datetime.fromtimestamp(conv.created_at).isoformat(),
                'updated_at': datetime.fromtimestamp(conv.updated_at).isoformat(),
                'metadata': conv.metadata
            }


# Singleton instance
_context_manager = None

def get_context_manager(config: Optional[Dict] = None) -> ContextManager:
    """Get or create the context manager singleton"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager(config)
    return _context_manager