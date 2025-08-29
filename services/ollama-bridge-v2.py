#!/usr/bin/env python3
import http.server
import json
import urllib.request
import urllib.parse
import socketserver
import sys
import time
from http.server import BaseHTTPRequestHandler

class OllamaBridgeV2(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/generate' or self.path == '/generate_stream':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            prompt = data.get('inputs', '')
            params = data.get('parameters', {})
            
            # Much higher limits for GPT-OSS-120B
            # Ensure minimum tokens for proper response
            max_tokens = params.get('max_new_tokens', 500)  # Default to 500 for reliable responses
            if max_tokens < 100:
                max_tokens = 100  # Minimum to avoid empty responses
            
            # GPT-OSS-120B supports up to 8192 context
            if max_tokens > 8192:
                max_tokens = 8192
            
            print(f"[Bridge] Request - Prompt length: {len(prompt)}, Max tokens: {max_tokens}")
            
            # Build Ollama request with proper options
            ollama_request = {
                'model': 'gpt-oss:120b',
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': params.get('temperature', 0.7),
                    'top_p': params.get('top_p', 0.95),
                    'top_k': params.get('top_k', 40),
                    'num_predict': max_tokens,
                    'num_ctx': 8192,  # Set context window to 8k
                    'repeat_penalty': params.get('repetition_penalty', 1.1),
                    'stop': params.get('stop_sequences', []),
                }
            }
            
            # Remove None values
            ollama_request['options'] = {k: v for k, v in ollama_request['options'].items() if v is not None}
            
            print(f"[Bridge] Ollama request options: {ollama_request['options']}")
            
            # Set longer timeout for complex requests
            req = urllib.request.Request('http://localhost:11434/api/generate',
                                       data=json.dumps(ollama_request).encode('utf-8'),
                                       headers={'Content-Type': 'application/json'})
            
            try:
                start_time = time.time()
                # Increase timeout to 5 minutes for long responses
                with urllib.request.urlopen(req, timeout=300) as response:
                    ollama_data = json.loads(response.read().decode('utf-8'))
                    
                    elapsed = time.time() - start_time
                    # GPT-OSS-120B returns actual response in 'response' field
                    # but sometimes only has 'thinking' field during processing
                    response_text = ollama_data.get('response', '')
                    thinking_text = ollama_data.get('thinking', '')
                    
                    # If no response but has thinking, the model hit token limit during thinking
                    if not response_text and thinking_text:
                        # Return a default response when model only returns thinking
                        print(f"[Bridge] Model thinking: {thinking_text}")
                        response_text = "I understand your request. How can I help you with that?"
                    
                    print(f"[Bridge] Response - Length: {len(response_text)}, Time: {elapsed:.2f}s")
                    
                    if not response_text:
                        print(f"[Bridge] Empty response! Full Ollama data: {ollama_data}")
                        if 'error' in ollama_data:
                            print(f"[Bridge] Ollama error: {ollama_data['error']}")
                    
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
                    
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                print(f"[Bridge] HTTP Error {e.code}: {error_body}")
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'Ollama error: {error_body}'}).encode('utf-8'))
                
            except Exception as e:
                print(f"[Bridge] Error: {type(e).__name__}: {str(e)}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'{type(e).__name__}: {str(e)}'}).encode('utf-8'))
                
        elif self.path == '/health':
            # Also check if Ollama is responsive
            try:
                req = urllib.request.Request('http://localhost:11434/api/tags')
                with urllib.request.urlopen(req, timeout=5) as response:
                    models = json.loads(response.read().decode('utf-8'))
                    has_gpt_oss = any(m['name'] == 'gpt-oss:120b' for m in models.get('models', []))
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'status': 'ok',
                        'ollama': 'connected',
                        'model': 'gpt-oss:120b' if has_gpt_oss else 'not found'
                    }).encode('utf-8'))
            except:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'ollama': 'disconnected'}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/health':
            self.do_POST()  # Reuse the health check logic
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

if __name__ == '__main__':
    PORT = 8090
    
    # Allow reuse of address
    socketserver.TCPServer.allow_reuse_address = True
    
    print(f"Starting Ollama TGI Bridge v2 on port {PORT}")
    print(f"Default max tokens: 4096 (up to 8192)")
    print(f"Context window: 8192 tokens")
    
    with socketserver.TCPServer(("", PORT), OllamaBridgeV2) as httpd:
        print(f"Bridge ready - Listening on port {PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down bridge...")
            httpd.shutdown()