from typing import Optional, Dict, Any
from dataclasses import dataclass
import asyncio
import json
from datetime import datetime
import uuid
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from mcp_servers.multiMCP import MultiMCP
from agent.model_manager import ModelManager
from utils.utils import log_error
from config.log_config import setup_logging
from utils.json_parser import parse_llm_json

log = setup_logging(__name__)

class BrowserAgent:
    def __init__(self, multi_mcp: MultiMCP):
        """
        Initialize the browser agent with required components
        
        Args:
            multi_mcp: MultiMCP instance for tool execution
        """
        log.info("Initializing BrowserAgent components...")
        self.multi_mcp = multi_mcp
        self.model = ModelManager()
        self.session_id = str(uuid.uuid4())
        log.info(f"BrowserAgent initialized with session ID: {self.session_id}")
        
    async def run(self, query: str) -> str:
        """
        Execute browser operations based on user query
        
        Args:
            query: User's browser-related query
            
        Returns:
            str: Result of the operation
        """
        try:
            log.info("Starting browser operation...")
            
            # 1. Get available browser tools
            log.info("Retrieving available browser tools...")
            tools = await self.multi_mcp.list_all_tools()
            if not tools:
                log_error("No browser tools available", "Please check MCP server configuration")
                return "No browser tools available. Please check MCP server configuration."
            
            log.info(f"Available tools: {tools}")
            
            # 2. Plan steps using the model
            log.info("Planning browser operation steps...")
            plan = await self._plan_steps(query, tools)
            log.info(f"Planned {len(plan['steps'])} steps")
            log.info(f"📋 Planned steps: {json.dumps(plan, indent=2)}")
            
            # 3. Execute each step
            for i, step in enumerate(plan["steps"], 1):
                log.info(f"Executing step {i}/{len(plan['steps'])}: {step['action']}")
                result = await self._execute_step(step)
                if not result["success"]:
                    log_error(f"Step {i} failed", result["error"])
                    return f"Failed to execute step: {result['error']}"
                log.info(f"Step {i} completed successfully")
                    
            log.info("Browser operation completed successfully")
            return plan["summary"]
            
        except Exception as e:
            log_error("Browser operation failed", e)
            return f"Browser operation failed: {str(e)}"
            
    async def _plan_steps(self, query: str, tools: list) -> Dict[str, Any]:
        """Plan browser operations using LLM"""
        # Get tool descriptions in the same format as decision.py
        function_list_text = self.multi_mcp.tool_description_wrapper()
        tool_descriptions = "\n".join(f"- `{desc.strip()}`" for desc in function_list_text)
        tool_descriptions = "\n\n### The ONLY Available Tools\n\n---\n\n" + tool_descriptions

        prompt = f"""
        You are a browser automation expert. Given the following browser query and available tools, plan the steps needed.
        Return ONLY a valid JSON object with no additional text.

        Query: {query}
        
        {tool_descriptions}
        
        Required JSON format:
        {{
            "steps": [
                {{
                    "action": "string describing the action",
                    "tool": "MUST be one of the tool names listed above",
                    "parameters": {{
                        "param1": "value1",
                        "param2": "value2"
                    }}
                }}
            ],
            "summary": "Brief description of what will be done"
        }}

        Example for opening a URL:
        {{
            "steps": [
                {{
                    "action": "Open URL in new tab",
                    "tool": "open_new_tab",
                    "parameters": {{
                        "url": "https://example.com"
                    }}
                }}
            ],
            "summary": "Open example.com in a new tab"
        }}
        """
        
        try:
            response = await self.model.generate_text(prompt)
            log.info(f"Model response: {response}")
            
            # Use the parse_llm_json utility to handle the response
            plan = parse_llm_json(response, required_keys=["steps", "summary"])
            
            # Validate the plan structure
            if not isinstance(plan.get("steps"), list):
                raise ValueError("Steps must be a list")
                
            for step in plan["steps"]:
                if not all(k in step for k in ["action", "tool", "parameters"]):
                    raise ValueError("Each step must have action, tool, and parameters")
                if step["tool"] not in tools:
                    raise ValueError(f"Tool '{step['tool']}' not in available tools: {tools}")
                    
            return plan
            
        except Exception as e:
            log_error(f"Failed to parse model response: {str(e)}")
            # Return a default plan for common operations
            return {
                "steps": [
                    {
                        "action": "Open URL in new tab",
                        "tool": "open_new_tab",
                        "parameters": {"url": query.split()[1] if "http" in query else f"https://{query.split()[1]}"}
                    }
                ],
                "summary": "Basic navigation operation"
            }
        
    async def _execute_step(self, step: Dict) -> Dict:
        log.info("=== Executing Step ===")
        log.info(f"Step details: {json.dumps(step, indent=2)}")
        
        try:
            tool_name = step.get("tool")
            if not tool_name:
                log.error("❌ No tool specified in step")
                return {"success": False, "error": "No tool specified"}
            
            parameters = step.get("parameters", {})
            log.info(f"Calling tool '{tool_name}' with parameters: {json.dumps(parameters, indent=2)}")
            
            result = await self.multi_mcp.call_tool(tool_name, arguments=parameters)
            
            # Convert CallToolResult to a serializable format
            result_dict = {
                "success": True,
                "result": {
                    "output": str(result.output) if hasattr(result, 'output') else None,
                    "error": str(result.error) if hasattr(result, 'error') else None,
                    "status": str(result.status) if hasattr(result, 'status') else None
                }
            }
            
            log.info(f"Tool execution result: {json.dumps(result_dict, indent=2)}")
            return result_dict
            
        except Exception as e:
            log.error(f"❌ Step execution failed: {str(e)}")
            log.error(f"Error type: {type(e)}")
            import traceback
            log.error(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}
