#!/usr/bin/env python3
"""
Final integrated tool system for GPT-OSS-20B
Combines all approaches for maximum reliability
"""

import json
import re
import requests
import subprocess
from typing import Dict, Any, Optional


class GPTOSSFinalToolSystem:
    """Production-ready tool system for GPT-OSS-20B"""
    
    def __init__(self, model_name: str = "gpt-oss-tools"):
        self.model = model_name  # Use the enhanced model we created
        self.ollama_url = "http://localhost:11434"
        self.tools_api = "http://localhost:8091"
        
    def query(self, prompt: str) -> str:
        """Main entry point for queries"""
        
        # First, try to get response from enhanced model
        response = self._query_model(prompt)
        
        # Check if model requested a tool
        tool_request = self._extract_tool_request(response)
        
        if tool_request:
            # Execute the tool
            tool_result = self._execute_tool(tool_request)
            
            # Format final response
            return self._format_tool_response(prompt, tool_request, tool_result)
        
        # If no tool needed, check if we should execute one anyway
        if self._should_use_tool(prompt):
            tool_result = self._smart_tool_execution(prompt)
            if tool_result:
                return tool_result
        
        # Return model response
        return response if response else "I understand your request but couldn't generate a response."
    
    def _query_model(self, prompt: str) -> str:
        """Query the Ollama model"""
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 500,
                        "temperature": 0.3
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')
                
        except Exception as e:
            print(f"Model query error: {e}")
        
        return ""
    
    def _extract_tool_request(self, response: str) -> Optional[Dict]:
        """Extract tool request from model response"""
        
        # Look for TOOL: format
        pattern = r'TOOL:(\w+):(.+?)(?:\n|$)'
        match = re.search(pattern, response)
        
        if match:
            return {
                'tool': match.group(1),
                'params': match.group(2).strip()
            }
        
        return None
    
    def _should_use_tool(self, prompt: str) -> bool:
        """Determine if a tool should be used based on prompt"""
        
        prompt_lower = prompt.lower()
        
        tool_indicators = {
            'calculate': ['calculate', 'what is', 'plus', 'minus', 'times', 'divided'],
            'read_file': ['read', 'file', 'show', '/etc/', '/home/'],
            'execute_command': ['date', 'time', 'hostname', 'whoami', 'system'],
            'web_search': ['search', 'find', 'look up', 'information about']
        }
        
        for tool, indicators in tool_indicators.items():
            if any(ind in prompt_lower for ind in indicators):
                return True
        
        return False
    
    def _smart_tool_execution(self, prompt: str) -> Optional[str]:
        """Execute tool based on prompt analysis"""
        
        prompt_lower = prompt.lower()
        
        # Calculate
        if any(word in prompt_lower for word in ['calculate', 'plus', 'minus', 'times', 'divided', 'sqrt']):
            expression = self._extract_math(prompt)
            if expression:
                result = self._execute_calculation(expression)
                return f"The result of {expression} is {result}"
        
        # File reading
        if any(word in prompt_lower for word in ['read', 'file', '/etc/', '/home/']):
            path = self._extract_path(prompt)
            if path:
                content = self._read_file(path)
                return f"Contents of {path}:\n{content}"
        
        # Commands
        if any(word in prompt_lower for word in ['date', 'time', 'hostname', 'whoami']):
            command = self._determine_command(prompt_lower)
            output = self._execute_command(command)
            return f"{command} output:\n{output}"
        
        return None
    
    def _execute_tool(self, tool_request: Dict) -> Any:
        """Execute a tool via API"""
        
        tool_name = tool_request['tool']
        params = tool_request['params']
        
        # Map to our tool API
        if tool_name == 'calculate':
            return self._execute_calculation(params)
        elif tool_name == 'read_file':
            return self._read_file(params)
        elif tool_name == 'execute_command':
            return self._execute_command(params)
        elif tool_name == 'web_search':
            return f"Search results for '{params}'"
        
        return "Unknown tool"
    
    def _execute_calculation(self, expression: str) -> float:
        """Execute calculation"""
        
        try:
            # Try API first
            response = requests.post(
                f"{self.tools_api}/tools/execute",
                json={"tool": "calculate", "arguments": {"expression": expression}},
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return result.get('result')
        except:
            pass
        
        # Fallback to eval
        try:
            import math
            safe_dict = {'sqrt': math.sqrt, 'pi': math.pi}
            return eval(expression, {"__builtins__": {}}, safe_dict)
        except:
            return "Error"
    
    def _read_file(self, path: str) -> str:
        """Read file contents"""
        
        try:
            with open(path, 'r') as f:
                return f.read()[:500]
        except Exception as e:
            return f"Error: {e}"
    
    def _execute_command(self, command: str) -> str:
        """Execute system command"""
        
        safe_commands = ['date', 'hostname', 'whoami', 'pwd', 'ls', 'echo']
        
        if command.split()[0] not in safe_commands:
            return "Command not allowed"
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, 
                                  text=True, timeout=5)
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error: {e}"
    
    def _extract_math(self, text: str) -> str:
        """Extract math expression from text"""
        
        text = text.lower()
        for remove in ['what is', 'calculate', 'compute']:
            text = text.replace(remove, '')
        
        text = text.replace('plus', '+').replace('minus', '-')
        text = text.replace('times', '*').replace('divided by', '/')
        
        # Clean up
        text = re.sub(r'[^0-9+\-*/().\s]', '', text).strip()
        
        return text if text else "0"
    
    def _extract_path(self, text: str) -> str:
        """Extract file path from text"""
        
        matches = re.findall(r'(/[\w/\-\.]+)', text)
        return matches[0] if matches else '/etc/hostname'
    
    def _determine_command(self, text: str) -> str:
        """Determine command from text"""
        
        if 'date' in text or 'time' in text:
            return 'date'
        elif 'hostname' in text:
            return 'hostname'
        elif 'whoami' in text:
            return 'whoami'
        else:
            return 'date'
    
    def _format_tool_response(self, prompt: str, tool_request: Dict, result: Any) -> str:
        """Format response with tool result"""
        
        tool = tool_request['tool']
        
        if tool == 'calculate':
            return f"The result is {result}"
        elif tool == 'read_file':
            return f"File contents:\n{result}"
        elif tool == 'execute_command':
            return f"Command output:\n{result}"
        else:
            return str(result)


def main():
    """Interactive mode"""
    
    print("="*60)
    print("GPT-OSS-20B Final Tool System")
    print("="*60)
    print("\nThis system combines:")
    print("  • Enhanced Ollama model with tool instructions")
    print("  • Smart intent detection")
    print("  • Direct tool execution")
    print("  • Fallback mechanisms")
    print("\nExamples:")
    print("  What is 25 times 4?")
    print("  Read the /etc/hostname file")
    print("  What's the current date?")
    print("\nType 'quit' to exit\n")
    
    system = GPTOSSFinalToolSystem()
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit']:
            break
        
        response = system.query(user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()