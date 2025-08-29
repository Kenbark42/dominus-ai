#!/usr/bin/env python3
"""
Enhanced Ollama Bridge with Tool-Use Support for GPT-OSS-20B
Extends the existing bridge to support function calling and tool execution
"""

import http.server
import json
import urllib.request
import urllib.parse
import socketserver
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional

# Import the tool system
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tool_system import (
    ToolRegistry, ToolExecutor, ToolCallParser, 
    ToolUsePromptFormatter, create_builtin_tools
)

# Import GPT-OSS-20B optimized prompting
try:
    from gpt_oss_prompts import GPTOSSPromptOptimizer
    gpt_oss_optimizer = GPTOSSPromptOptimizer()
except ImportError:
    gpt_oss_optimizer = None
    print("[Warning] GPT-OSS prompt optimizer not available")


class OllamaBridgeWithTools(BaseHTTPRequestHandler):
    # Class-level tool registry shared across requests
    tool_registry = create_builtin_tools()
    tool_executor = ToolExecutor(tool_registry)
    tool_parser = ToolCallParser()
    prompt_formatter = ToolUsePromptFormatter()
    
    def do_POST(self):
        if self.path == '/generate' or self.path == '/generate_stream':
            self.handle_generate()
        elif self.path == '/generate_with_tools':
            self.handle_generate_with_tools()
        elif self.path == '/tools/list':
            self.handle_list_tools()
        elif self.path == '/tools/execute':
            self.handle_execute_tool()
        elif self.path == '/health':
            self.handle_health()
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_generate(self):
        """Standard generation without tool support"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        prompt = data.get('inputs', '')
        params = data.get('parameters', {})
        
        max_tokens = params.get('max_new_tokens', 2048)
        if max_tokens > 8192:
            max_tokens = 8192
        
        print(f"[Bridge] Standard request - Prompt length: {len(prompt)}, Max tokens: {max_tokens}")
        
        ollama_request = {
            'model': 'gpt-oss:20b',
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': params.get('temperature', 0.7),
                'top_p': params.get('top_p', 0.95),
                'top_k': params.get('top_k', 40),
                'num_predict': max_tokens,
                'num_ctx': 8192,
                'repeat_penalty': params.get('repetition_penalty', 1.1),
                'stop': params.get('stop_sequences', []),
            }
        }
        
        ollama_request['options'] = {k: v for k, v in ollama_request['options'].items() if v is not None}
        
        req = urllib.request.Request('http://localhost:11434/api/generate',
                                   data=json.dumps(ollama_request).encode('utf-8'),
                                   headers={'Content-Type': 'application/json'})
        
        try:
            start_time = time.time()
            with urllib.request.urlopen(req, timeout=300) as response:
                ollama_data = json.loads(response.read().decode('utf-8'))
                
                elapsed = time.time() - start_time
                response_text = ollama_data.get('response', '')
                
                print(f"[Bridge] Response - Length: {len(response_text)}, Time: {elapsed:.2f}s")
                
                result = {
                    'generated_text': response_text,
                    'details': {
                        'finish_reason': 'length' if len(response_text) >= max_tokens - 10 else 'stop',
                        'generated_tokens': len(response_text.split()),
                        'elapsed_time': elapsed
                    }
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                
        except Exception as e:
            print(f"[Bridge] Error: {type(e).__name__}: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
    
    def handle_generate_with_tools(self):
        """Enhanced generation with tool support"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        prompt = data.get('inputs', '')
        params = data.get('parameters', {})
        tools = data.get('tools', None)
        max_iterations = data.get('max_iterations', 5)
        
        # If specific tools are provided, use them; otherwise use all available
        if tools:
            # Get schemas in OpenAI format
            all_schemas = self.tool_registry.get_all_schemas()
            available_tools = {name: all_schemas[name] 
                             for name in tools if name in all_schemas}
        else:
            available_tools = self.tool_registry.get_all_schemas()
        
        # Format the system prompt with tool information
        # Use GPT-OSS optimized prompting if available
        if gpt_oss_optimizer:
            system_prompt = gpt_oss_optimizer.format_tool_system_prompt(available_tools)
            # Add few-shot examples for better performance
            system_prompt += "\n" + gpt_oss_optimizer.format_few_shot_examples()
        else:
            system_prompt = self.prompt_formatter.format_system_prompt(available_tools)
        
        # Combine system prompt with user prompt
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        
        print(f"[Bridge] Tool-enhanced request - Tools: {list(available_tools.keys())}")
        
        # Conversation history for multi-turn tool use
        conversation = []
        final_response = ""
        tool_calls_made = []
        
        for iteration in range(max_iterations):
            # Generate response
            ollama_request = {
                'model': 'gpt-oss:20b',
                'prompt': full_prompt if iteration == 0 else self._build_continuation_prompt(conversation, prompt),
                'stream': False,
                'options': {
                    'temperature': params.get('temperature', 0.7),
                    'top_p': params.get('top_p', 0.95),
                    'top_k': params.get('top_k', 40),
                    'num_predict': params.get('max_new_tokens', 2048),
                    'num_ctx': 8192,
                    'repeat_penalty': params.get('repetition_penalty', 1.1),
                }
            }
            
            try:
                req = urllib.request.Request('http://localhost:11434/api/generate',
                                           data=json.dumps(ollama_request).encode('utf-8'),
                                           headers={'Content-Type': 'application/json'})
                
                with urllib.request.urlopen(req, timeout=300) as response:
                    ollama_data = json.loads(response.read().decode('utf-8'))
                    response_text = ollama_data.get('response', '')
                    
                    # Check for thinking (gpt-oss-20b specific)
                    thinking = ollama_data.get('thinking', '')
                    
                    # If response is empty but we have thinking, use thinking as response
                    # This is a workaround for gpt-oss-20b's behavior
                    if not response_text and thinking:
                        response_text = thinking
                        print(f"[Bridge] Using thinking as response (gpt-oss-20b workaround)")
                    
                    print(f"[Bridge] Iteration {iteration + 1} - Response length: {len(response_text)}")
                    if thinking and response_text != thinking:
                        print(f"[Bridge] Model thinking: {thinking[:100]}...")
                    
                    conversation.append({
                        'role': 'assistant',
                        'content': response_text,
                        'thinking': thinking
                    })
                    
                    # Parse tool calls from response
                    # Use GPT-OSS optimized parser if available
                    if gpt_oss_optimizer:
                        tool_calls = gpt_oss_optimizer.extract_tool_calls_from_response(response_text)
                    else:
                        tool_calls = self.tool_parser.parse_tool_calls(response_text)
                    
                    if not tool_calls:
                        # No tool calls found, this is the final response
                        final_response = response_text
                        break
                    
                    # Execute tool calls
                    for tool_call in tool_calls:
                        func_name = tool_call.get('function') or tool_call.get('tool')
                        arguments = tool_call.get('arguments', {})
                        
                        print(f"[Bridge] Executing tool: {func_name} with args: {arguments}")
                        
                        result = self.tool_executor.execute(func_name, arguments)
                        
                        tool_calls_made.append({
                            'tool': func_name,
                            'arguments': arguments,
                            'result': result
                        })
                        
                        # Add tool result to conversation
                        tool_result_msg = self.prompt_formatter.format_tool_result(result)
                        conversation.append({
                            'role': 'tool',
                            'content': tool_result_msg,
                            'tool_call': tool_call
                        })
                    
            except Exception as e:
                print(f"[Bridge] Error in iteration {iteration + 1}: {e}")
                final_response = f"Error during processing: {str(e)}"
                break
        
        # Prepare final result
        result = {
            'generated_text': final_response,
            'tool_calls': tool_calls_made,
            'conversation': conversation,
            'details': {
                'iterations': iteration + 1,
                'tools_used': list(set(tc['tool'] for tc in tool_calls_made)),
                'finish_reason': 'complete'
            }
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def _build_continuation_prompt(self, conversation: List[Dict], original_prompt: str) -> str:
        """Build a continuation prompt from conversation history"""
        prompt = f"User: {original_prompt}\n\n"
        
        for msg in conversation:
            if msg['role'] == 'assistant':
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg['role'] == 'tool':
                prompt += f"Tool Result: {msg['content']}\n\n"
        
        prompt += "Assistant: Based on the tool results above, "
        return prompt
    
    def handle_list_tools(self):
        """List available tools"""
        schemas = self.tool_registry.get_all_schemas()
        
        result = {
            'tools': list(schemas.keys()),
            'schemas': schemas
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def handle_execute_tool(self):
        """Direct tool execution endpoint"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))
        
        tool_name = data.get('tool')
        arguments = data.get('arguments', {})
        
        if not tool_name:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Tool name required'}).encode('utf-8'))
            return
        
        result = self.tool_executor.execute(tool_name, arguments)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))
    
    def handle_health(self):
        """Health check endpoint"""
        try:
            req = urllib.request.Request('http://localhost:11434/api/tags')
            with urllib.request.urlopen(req, timeout=5) as response:
                models = json.loads(response.read().decode('utf-8'))
                has_gpt_oss = any(m['name'] == 'gpt-oss:20b' for m in models.get('models', []))
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'ok',
                    'ollama': 'connected',
                    'model': 'gpt-oss:20b' if has_gpt_oss else 'not found',
                    'tools_enabled': True,
                    'available_tools': self.tool_registry.list_tools()
                }).encode('utf-8'))
        except Exception as e:
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'error',
                'ollama': 'disconnected',
                'error': str(e)
            }).encode('utf-8'))
    
    def do_GET(self):
        if self.path == '/health':
            self.handle_health()
        elif self.path == '/tools/list':
            self.handle_list_tools()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        # Log to stdout for debugging
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()


def add_custom_tools(registry: ToolRegistry):
    """Add custom tools specific to your darkfoo project"""
    # Import from the module we already imported
    from tool_system import ToolParameter, ParameterType
    
    # Darkfoo-specific tools
    def control_lights(state: str, brightness: int = 100) -> Dict:
        """Control smart home lights"""
        # This would integrate with your smart home system
        return {
            "action": "lights",
            "state": state,
            "brightness": brightness,
            "timestamp": time.time()
        }
    
    registry.register(
        name="control_lights",
        func=control_lights,
        description="Control smart home lighting",
        parameters=[
            ToolParameter(
                name="state",
                type=ParameterType.STRING,
                description="Light state (on/off/dim)",
                enum=["on", "off", "dim"]
            ),
            ToolParameter(
                name="brightness",
                type=ParameterType.INTEGER,
                description="Brightness level (0-100)",
                required=False,
                default=100
            )
        ]
    )
    
    def query_database(query: str, table: str = None) -> List[Dict]:
        """Query the darkfoo database"""
        # Placeholder for database integration
        return [
            {"message": "Database query placeholder", "query": query, "table": table}
        ]
    
    registry.register(
        name="query_database",
        func=query_database,
        description="Query the darkfoo database",
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="SQL query or natural language query"
            ),
            ToolParameter(
                name="table",
                type=ParameterType.STRING,
                description="Target table name",
                required=False
            )
        ]
    )


if __name__ == '__main__':
    PORT = 8091  # Different port to avoid conflict with existing bridge
    
    # Add custom tools
    add_custom_tools(OllamaBridgeWithTools.tool_registry)
    
    # Allow reuse of address
    socketserver.TCPServer.allow_reuse_address = True
    
    print(f"Starting Enhanced Ollama Bridge with Tool Support on port {PORT}")
    print(f"Available tools: {OllamaBridgeWithTools.tool_registry.list_tools()}")
    print(f"Endpoints:")
    print(f"  - POST /generate - Standard generation")
    print(f"  - POST /generate_with_tools - Tool-enhanced generation")
    print(f"  - GET/POST /tools/list - List available tools")
    print(f"  - POST /tools/execute - Execute a specific tool")
    print(f"  - GET /health - Health check")
    
    with socketserver.TCPServer(("", PORT), OllamaBridgeWithTools) as httpd:
        print(f"Bridge ready - Listening on port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down enhanced bridge...")
            httpd.shutdown()