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
from utils.utils import log_error, log_json_block
from config.log_config import setup_logging, logger_json_block
from utils.json_parser import parse_llm_json
from action.execute_step import execute_step_with_mode
from browser.browser_context import BrowserContext
from browser.browser_perception import BrowserPerception, build_browser_perception_input
from perception.perception import build_perception_input

log = setup_logging(__name__)

class StepType:
    ROOT = "ROOT"
    CODE = "CODE"

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
        
        # Initialize perception
        self.perception = BrowserPerception(
            perception_prompt_path="prompts/browser_agent_perception_prompt.txt"
        )
        
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
            
            # Initialize context
            self.ctx = BrowserContext(self.session_id, query)

            await self._run_initial_perception()

            log.info(f"Perception result: {self.p_out}")
                  
            # If perception suggests a different route, handle it
            if self.p_out["route"] != "browser":
                return f"Perception suggests this query should be handled by {self.p_out['route']} module"
            
            # Continue with existing browser operation logic...
            tools = await self.multi_mcp.list_all_tools()
            if not tools:
                log_error("No browser tools available", "Please check MCP server configuration")
                return "No browser tools available. Please check MCP server configuration."
            
            log.info(f"Available tools: {tools}")
            
            # 2. Plan steps using the model
            log.info("Planning browser operation steps...")
            plan = await self._plan_steps(query, tools)
            log.info(f"Planned {len(plan['plan_graph']['nodes'])} steps")
            log.info(f"📋 Planned steps: {json.dumps(plan, indent=2)}")
            
            # 4. Add steps to context
            for node in plan["plan_graph"]["nodes"]:
                self.ctx.add_step(
                    step_id=node["id"],
                    description=node["description"],
                    step_type=StepType.CODE
                )
            
            # Then add edges according to the plan
            for edge in plan["plan_graph"]["edges"]:
                self.ctx.graph.add_edge(edge["from"], edge["to"])
            
            # 5. Execute steps using execute_step_with_mode
            next_step_id = plan["next_step_id"]
            code_variants = plan["code_variants"]

            self.code_variants = plan["code_variants"]
            self.next_step_id = plan["next_step_id"]

            while True:
                if self.ctx.is_step_completed(next_step_id):
                    log.info(f"✅ Step {next_step_id} already completed. Skipping.")
                    # Find next uncompleted step
                    for node in plan["plan_graph"]["nodes"]:
                        if not self.ctx.is_step_completed(node["id"]):
                            next_step_id = node["id"]
                            break
                    else:
                        # All steps completed
                        break
                    continue
                
                log.info(f"Executing step {next_step_id}")
                success = await execute_step_with_mode(
                    next_step_id,
                    code_variants,
                    self.ctx,
                    "fallback",  # Use fallback mode
                    None,  # No session needed for browser operations
                    self.multi_mcp
                )
                
                if not success:
                    log.error(f"❌ Step {next_step_id} failed")
                    return f"Failed to execute step {next_step_id}"
                
                log.info(f"✅ Step {next_step_id} completed successfully")
                
                # Get next step from plan graph
                for edge in plan["plan_graph"]["edges"]:
                    if edge["from"] == next_step_id:
                        next_step_id = edge["to"]
                        break
                else:
                    # No more steps
                    break
            
            log.info("Browser operation completed successfully")
            return plan["summary"]
            
        except Exception as e:
            log_error("Browser operation failed", e)
            return f"Browser operation failed: {str(e)}"
            
    
    async def _run_initial_perception(self):
        p_input = build_perception_input(self.ctx.query, self.ctx.memory, self.ctx)
        log.info(f"📝 Initial Perception")
        logger_json_block(log,'Inital Perception input:', p_input)
        self.p_out = await self.perception.run(p_input, self.ctx)
        log.info(f"📝 Initial Perception output")
        logger_json_block(log,'Initial Perception output:', self.p_out)

        # This is not needed, because the root node is created in the BrowserContext constructor
        #self.ctx.add_step(step_id=StepType.ROOT, description="initial query", step_type=StepType.ROOT)
        self.ctx.mark_step_completed(StepType.ROOT)
        self.ctx.attach_perception(StepType.ROOT, self.p_out)

        log_json_block('📌 Perception output (ROOT)', self.p_out)
        self.ctx._print_graph(depth=2)
    
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
            "plan_graph": {{
                "nodes": [
                    {{ "id": "0", "description": "..." }},
                    {{ "id": "1", "description": "..." }}
                ],
                "edges": [
                    {{ "from": "ROOT", "to": "0", "type": "normal" }},
                    {{ "from": "0", "to": "1", "type": "normal" }}
                ]
            }},
            "next_step_id": "0",
            "code_variants": {{
                "CODE_0A": "<code block>",
                "CODE_0B": "<code block>",
                "CODE_0C": "<code block>"
            }}
        }}

        Rules:
        1. Each code block must be raw Python code (no await, no def, no markdown)
        2. Each code block must end with a return statement like:
           return {{ "result_0A": value }}
        3. Use different strategies in each variant
        4. No import statements, only use provided tools
        5. No keyword arguments, use positional arguments only

        Example for opening a URL:
        {{
            "plan_graph": {{
                "nodes": [
                    {{ "id": "0", "description": "Open URL in new tab" }}
                ],
                "edges": [
                    {{ "from": "ROOT", "to": "0", "type": "normal" }}
                ]
            }},
            "next_step_id": "0",
            "code_variants": {{
                "CODE_0A": "result = open_tab('https://example.com')\nreturn {{ 'result_0A': result }}",
                "CODE_0B": "result = go_to_url('https://example.com')\nreturn {{ 'result_0B': result }}",
                "CODE_0C": "result = search_google('example.com')\nreturn {{ 'result_0C': result }}"
            }}
        }}
        """
        
        try:
            response = await self.model.generate_text(prompt)
            log.info(f"Model response: {response}")
            
            # Use parse_llm_json to handle the response
            plan = parse_llm_json(response, required_keys=["plan_graph", "next_step_id", "code_variants"])
            
            # Validate the plan structure
            if not isinstance(plan.get("plan_graph", {}).get("nodes"), list):
                raise ValueError("Plan graph nodes must be a list")
                
            for node in plan["plan_graph"]["nodes"]:
                if not all(k in node for k in ["id", "description"]):
                    raise ValueError("Each node must have id and description")
                    
            if not isinstance(plan.get("code_variants"), dict):
                raise ValueError("Code variants must be a dictionary")
                
            for suffix in ["A", "B", "C"]:
                variant_key = f"CODE_{plan['next_step_id']}{suffix}"
                if variant_key not in plan["code_variants"]:
                    raise ValueError(f"Missing code variant {variant_key}")
                    
            return plan
                
        except Exception as e:
            log_error(f"Failed to parse model response: {str(e)}")
            # Return a default plan for common operations
            return {
                "plan_graph": {
                    "nodes": [
                        {
                            "id": "0",
                            "description": "Open URL in new tab"
                        }
                    ],
                    "edges": [
                        {
                            "from": "ROOT",
                            "to": "0",
                            "type": "normal"
                        }
                    ]
                },
                "next_step_id": "0",
                "code_variants": {
                    "CODE_0A": f"result = open_tab('{query.split()[1] if 'http' in query else f'https://{query.split()[1]}'}')\nreturn {{ 'result_0A': result }}",
                    "CODE_0B": f"result = go_to_url('{query.split()[1] if 'http' in query else f'https://{query.split()[1]}'}')\nreturn {{ 'result_0B': result }}",
                    "CODE_0C": f"result = search_google('{query.split()[1] if 'http' in query else f'https://{query.split()[1]}'}')\nreturn {{ 'result_0C': result }}"
                }
            }
