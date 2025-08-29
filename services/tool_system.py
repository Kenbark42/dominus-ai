#!/usr/bin/env python3
"""
Tool-Use System for GPT-OSS-20B
Enables function calling and tool execution for agentic capabilities
"""

import json
import re
import inspect
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import traceback


class ParameterType(Enum):
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    items: Optional[Dict] = None  # For array types
    properties: Optional[Dict] = None  # For object types


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: List[ToolParameter]
    returns: Optional[str] = None
    examples: Optional[List[Dict]] = None


class ToolRegistry:
    """Registry for managing available tools"""
    
    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self.schemas: Dict[str, ToolSchema] = {}
        
    def register(self, 
                 name: str,
                 func: Callable,
                 description: str,
                 parameters: List[ToolParameter],
                 returns: Optional[str] = None,
                 examples: Optional[List[Dict]] = None):
        """Register a tool with its schema"""
        
        schema = ToolSchema(
            name=name,
            description=description,
            parameters=parameters,
            returns=returns,
            examples=examples
        )
        
        self.tools[name] = {
            'function': func,
            'schema': schema
        }
        self.schemas[name] = schema
        
    def get_tool(self, name: str) -> Optional[Dict]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def get_schema(self, name: str) -> Optional[ToolSchema]:
        """Get tool schema by name"""
        return self.schemas.get(name)
    
    def list_tools(self) -> List[str]:
        """List all available tool names"""
        return list(self.tools.keys())
    
    def get_all_schemas(self) -> Dict[str, Dict]:
        """Get all tool schemas in OpenAI-compatible format"""
        schemas = {}
        for name, schema in self.schemas.items():
            schemas[name] = self._schema_to_openai_format(schema)
        return schemas
    
    def _schema_to_openai_format(self, schema: ToolSchema) -> Dict:
        """Convert internal schema to OpenAI function calling format"""
        properties = {}
        required = []
        
        for param in schema.parameters:
            prop = {
                "type": param.type.value,
                "description": param.description
            }
            
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items
            if param.properties:
                prop["properties"] = param.properties
                
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": schema.name,
                "description": schema.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolExecutor:
    """Executes tools based on parsed function calls"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        
    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given arguments"""
        
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {
                "error": f"Tool '{tool_name}' not found",
                "available_tools": self.registry.list_tools()
            }
        
        try:
            # Validate arguments against schema
            schema = tool['schema']
            validated_args = self._validate_arguments(arguments, schema)
            
            # Execute the function
            func = tool['function']
            result = func(**validated_args)
            
            return {
                "success": True,
                "result": result,
                "tool": tool_name
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tool": tool_name,
                "arguments": arguments
            }
    
    def _validate_arguments(self, arguments: Dict[str, Any], schema: ToolSchema) -> Dict[str, Any]:
        """Validate and coerce arguments based on schema"""
        
        validated = {}
        
        for param in schema.parameters:
            if param.name in arguments:
                value = arguments[param.name]
                # Basic type coercion
                if param.type == ParameterType.INTEGER:
                    value = int(value)
                elif param.type == ParameterType.NUMBER:
                    value = float(value)
                elif param.type == ParameterType.BOOLEAN:
                    value = bool(value)
                elif param.type == ParameterType.STRING:
                    value = str(value)
                    
                validated[param.name] = value
            elif param.required:
                if param.default is not None:
                    validated[param.name] = param.default
                else:
                    raise ValueError(f"Required parameter '{param.name}' not provided")
        
        return validated


class ToolCallParser:
    """Parses tool calls from LLM responses"""
    
    @staticmethod
    def parse_tool_calls(response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from response text.
        Supports multiple formats:
        1. JSON function calls
        2. XML-style tags
        3. Natural language with clear intent
        """
        
        tool_calls = []
        
        # Try JSON format first
        json_pattern = r'```json\s*(\{.*?"function".*?\})\s*```'
        json_matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in json_matches:
            try:
                call = json.loads(match)
                if 'function' in call or 'tool' in call:
                    tool_calls.append(call)
            except json.JSONDecodeError:
                pass
        
        # Try XML-style format
        xml_pattern = r'<tool>(.*?)</tool>'
        xml_matches = re.findall(xml_pattern, response, re.DOTALL)
        
        for match in xml_matches:
            # Parse XML-style content
            name_match = re.search(r'<name>(.*?)</name>', match)
            args_match = re.search(r'<arguments>(.*?)</arguments>', match, re.DOTALL)
            
            if name_match:
                try:
                    args = {}
                    if args_match:
                        # Try to parse as JSON
                        try:
                            args = json.loads(args_match.group(1))
                        except:
                            # Parse as key-value pairs
                            arg_pattern = r'<(\w+)>(.*?)</\1>'
                            for key, value in re.findall(arg_pattern, args_match.group(1)):
                                args[key] = value
                    
                    tool_calls.append({
                        'function': name_match.group(1),
                        'arguments': args
                    })
                except:
                    pass
        
        # Try inline function call format
        inline_pattern = r'(\w+)\((.*?)\)'
        inline_matches = re.findall(inline_pattern, response)
        
        for func_name, args_str in inline_matches:
            # Check if this looks like a function call
            if func_name in ['calculate', 'search', 'fetch', 'get', 'post', 'execute']:
                try:
                    # Parse arguments
                    args = {}
                    if args_str:
                        # Simple key=value parsing
                        for arg in args_str.split(','):
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key.strip()] = value.strip().strip('"\'')
                    
                    tool_calls.append({
                        'function': func_name,
                        'arguments': args
                    })
                except:
                    pass
        
        return tool_calls


class ToolUsePromptFormatter:
    """Formats prompts to include tool information"""
    
    @staticmethod
    def format_system_prompt(tools: Dict[str, Dict]) -> str:
        """Create system prompt with tool descriptions"""
        
        prompt = """You are an AI assistant with access to the following tools:

"""
        
        for name, schema in tools.items():
            func_schema = schema['function']
            prompt += f"### {func_schema['name']}\n"
            prompt += f"Description: {func_schema['description']}\n"
            
            if func_schema['parameters']['properties']:
                prompt += "Parameters:\n"
                for param_name, param_info in func_schema['parameters']['properties'].items():
                    required = param_name in func_schema['parameters'].get('required', [])
                    req_str = " (required)" if required else " (optional)"
                    prompt += f"  - {param_name}: {param_info['type']}{req_str} - {param_info.get('description', '')}\n"
            
            prompt += "\n"
        
        prompt += """
To use a tool, format your response as:

```json
{
  "function": "tool_name",
  "arguments": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

You can also use XML format:
<tool>
  <name>tool_name</name>
  <arguments>
    <param1>value1</param1>
    <param2>value2</param2>
  </arguments>
</tool>

Always explain what you're doing before and after tool calls.
"""
        
        return prompt
    
    @staticmethod
    def format_tool_result(result: Dict[str, Any]) -> str:
        """Format tool execution result for context"""
        
        if result.get('success'):
            return f"Tool '{result['tool']}' returned: {json.dumps(result['result'], indent=2)}"
        else:
            return f"Tool '{result['tool']}' failed: {result.get('error', 'Unknown error')}"


# Example built-in tools
def create_builtin_tools() -> ToolRegistry:
    """Create registry with built-in tools"""
    
    registry = ToolRegistry()
    
    # Calculator tool
    def calculate(expression: str) -> float:
        """Evaluate a mathematical expression"""
        import math
        import re
        
        # Create a safe namespace with math functions
        safe_dict = {
            'pi': math.pi,
            'e': math.e,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'pow': math.pow,
            'abs': abs,
            'round': round,
            'floor': math.floor,
            'ceil': math.ceil,
        }
        
        # Replace ^ with ** for power operations
        expression = expression.replace('^', '**')
        
        # Basic safety check - only allow certain characters
        if re.search(r'[^0-9+\-*/().,\s\w]', expression):
            # Check if it contains only safe function names
            for func in safe_dict.keys():
                expression = expression.replace(func, f'safe_dict["{func}"]')
        
        try:
            # Use eval with restricted namespace
            result = eval(expression, {"__builtins__": {}, "safe_dict": safe_dict}, safe_dict)
            return float(result)
        except Exception as e:
            raise ValueError(f"Invalid expression: {expression} - {str(e)}")
    
    registry.register(
        name="calculate",
        func=calculate,
        description="Perform mathematical calculations",
        parameters=[
            ToolParameter(
                name="expression",
                type=ParameterType.STRING,
                description="Mathematical expression to evaluate (e.g., '2 + 2', '10 * 5')"
            )
        ],
        returns="The result of the calculation",
        examples=[
            {"expression": "2 + 2", "result": 4},
            {"expression": "10 * 5", "result": 50}
        ]
    )
    
    # Web search tool (placeholder)
    def web_search(query: str, max_results: int = 5) -> List[Dict]:
        """Search the web for information"""
        # This would integrate with a real search API
        return [
            {
                "title": f"Search result for: {query}",
                "snippet": "This is a placeholder result. Integrate with a real search API.",
                "url": "https://example.com"
            }
        ]
    
    registry.register(
        name="web_search",
        func=web_search,
        description="Search the web for information",
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="Search query"
            ),
            ToolParameter(
                name="max_results",
                type=ParameterType.INTEGER,
                description="Maximum number of results",
                required=False,
                default=5
            )
        ],
        returns="List of search results"
    )
    
    # File operations tool
    def read_file(path: str) -> str:
        """Read contents of a file"""
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            raise ValueError(f"Failed to read file: {e}")
    
    registry.register(
        name="read_file",
        func=read_file,
        description="Read the contents of a file",
        parameters=[
            ToolParameter(
                name="path",
                type=ParameterType.STRING,
                description="Path to the file"
            )
        ],
        returns="File contents as string"
    )
    
    # System command tool (use with caution)
    def execute_command(command: str, safe_mode: bool = True) -> str:
        """Execute a system command"""
        import subprocess
        
        if safe_mode:
            # Only allow certain safe commands
            safe_commands = ['ls', 'pwd', 'date', 'echo', 'cat', 'grep', 'find']
            cmd_parts = command.split()
            if not cmd_parts or cmd_parts[0] not in safe_commands:
                raise ValueError(f"Command '{cmd_parts[0] if cmd_parts else ''}' not allowed in safe mode")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            raise ValueError("Command timed out")
        except Exception as e:
            raise ValueError(f"Command failed: {e}")
    
    registry.register(
        name="execute_command",
        func=execute_command,
        description="Execute a system command",
        parameters=[
            ToolParameter(
                name="command",
                type=ParameterType.STRING,
                description="Command to execute"
            ),
            ToolParameter(
                name="safe_mode",
                type=ParameterType.BOOLEAN,
                description="Only allow safe commands",
                required=False,
                default=True
            )
        ],
        returns="Command output"
    )
    
    return registry


if __name__ == "__main__":
    # Example usage
    print("Tool System for GPT-OSS-20B initialized")
    
    # Create registry with built-in tools
    registry = create_builtin_tools()
    
    # Create executor
    executor = ToolExecutor(registry)
    
    # Get all schemas
    schemas = registry.get_all_schemas()
    print("\nAvailable tools:")
    for name in schemas:
        print(f"  - {name}")
    
    # Create system prompt
    formatter = ToolUsePromptFormatter()
    system_prompt = formatter.format_system_prompt(schemas)
    print("\nSystem prompt preview:")
    print(system_prompt[:500] + "...")
    
    # Test tool execution
    print("\nTesting calculator tool:")
    result = executor.execute("calculate", {"expression": "2 + 2"})
    print(f"Result: {result}")
    
    # Test parsing
    parser = ToolCallParser()
    test_response = """
    I'll calculate that for you.
    
    ```json
    {
      "function": "calculate",
      "arguments": {
        "expression": "10 * 5"
      }
    }
    ```
    """
    
    calls = parser.parse_tool_calls(test_response)
    print(f"\nParsed tool calls: {calls}")