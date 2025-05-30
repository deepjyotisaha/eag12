from typing import Optional, Dict, Any
from dataclasses import dataclass
import asyncio
import json
from datetime import datetime
import uuid
import sys
from pathlib import Path
import yaml

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from mcp_servers.multiMCP import MultiMCP
from agent.model_manager import ModelManager
from utils.utils import log_error, log_json_block, log_step
from config.log_config import setup_logging, logger_json_block
from utils.json_parser import parse_llm_json
from action.execute_step import execute_step_with_mode
from browser.browser_context import BrowserContext
from browser.browser_perception import BrowserPerception, build_browser_perception_input
from perception.perception import build_perception_input
from browser.browser_decision import BrowserDecision, build_browser_decision_input
from browser.browser_summarize import BrowserAgentSummarizer
from mcp_servers.multiMCP import MultiMCP

log = setup_logging(__name__)

class StepType:
    ROOT = "ROOT"
    BROWSEROPERATION = "BROWSEROPERATION"

class Route:
    SUMMARIZE = "summarize"
    BROWSER = "browser"

class BrowserAgent:
    def __init__(self, multi_mcp: MultiMCP):
        """
        Initialize the browser agent with required components
        
        Args:
            multi_mcp: MultiMCP instance for tool execution
        """
        log.info("Initializing BrowserAgent components...")
        #self.multi_mcp = multi_mcp
        self.model = ModelManager()
        self.session_id = str(uuid.uuid4())
        log.info(f"BrowserAgent initialized with session ID: {self.session_id}")

        # Load MCP server configs
        config_path = Path("config/mcp_server_config.yaml")
        with open(config_path, "r") as f:
            profile = yaml.safe_load(f)
            mcp_servers_list = profile.get("mcp_servers", [])
            # Filter for webbrowsing server only
            browser_config = next(
                (server for server in mcp_servers_list if server["id"] == "webbrowsing"),
                None
            )
            if not browser_config:
                raise ValueError("Webbrowsing MCP server config not found")
            
        # Initialize MultiMCP with only the browser config
        log.info("Initializing MultiMCP with browser tools...")
        self.multi_mcp = MultiMCP(server_configs=[browser_config])
        
    async def run(self, query: str) -> dict:
        """
        Execute browser operations based on user query
        
        Args:
            query: User's browser-related query
            
        Returns:
            dict: Result of the operation
        """
        try:
            log.info("Starting browser operation...")

            log_step("🌐 Starting browser operation with BrowserAgent 🌐")

            await self.multi_mcp.initialize()       
        
            # Initialize perception
            self.perception = BrowserPerception(
                perception_prompt_path="prompts/browser_agent_perception_prompt.txt"
            )
        
            # Initialize decision with both required parameters
            self.decision = BrowserDecision(
                decision_prompt_path="prompts/browser_agent_decision_prompt.txt",
                multi_mcp=self.multi_mcp
            )
        
            # Initialize summarizer with path
            self.summarizer = BrowserAgentSummarizer(
                summarizer_prompt_path="prompts/browser_agent_summarizer_prompt.txt"
            )
        
            # Log available tools and their details
            tools = await self.multi_mcp.list_all_tools()
            log.info(f"Successfully initialized MultiMCP with {len(tools)} tools")

            # Log tool descriptions in the same format as decision prompt
            log.info("\n=== Available Tools ===")
            function_list_text = self.multi_mcp.tool_description_wrapper()
            tool_descriptions = "\n".join(f"- `{desc.strip()}`" for desc in function_list_text)
            log.info("\n" + tool_descriptions)
            
            # Initialize context
            self.ctx = BrowserContext(self.session_id, query)

            await self._run_initial_perception()
                  
            log.info(f"Perception result: {self.p_out}")
                  
            # If perception suggests a different route, handle it
            if self.p_out["route"] != "browser":
                return {
                    "status": "failed",
                    "reason": f"Perception suggests this query should be handled by {self.p_out['route']} module",
                    "browser_operation": True
                }
            
            # Continue with existing browser operation logic...
            tools = await self.multi_mcp.list_all_tools()
            if not tools:
                log_error("No browser tools available", "Please check MCP server configuration")
                return {
                    "status": "failed",
                    "reason": "No browser tools available. Please check MCP server configuration.",
                    "browser_operation": True
                }
            
            log.info(f"Available tools: {tools}")
            
            # 2. Plan steps using the decision module
            plan = await self._plan_next_steps(query)
            
            # 5. Execute steps
            success = await self._execute_steps(plan)
            if not success:
                return {
                    "status": "failed",
                    "reason": "Failed to execute browser operation",
                    "browser_operation": True
                }
            
            # 6. Summarize and create final plan
            final_plan = await self.summarizer.summarize(query, self.ctx, self.p_out)
            log.info("Browser operation completed successfully")
            log_step("🌐 Browser operation completed successfully, handing over to Cortex Agent 🌐")
            
            return final_plan
            
        except Exception as e:
            log_error("Browser operation failed", e)
            return {
                "status": "failed",
                "reason": f"Browser operation failed: {str(e)}",
                "browser_operation": True
            }
            
    
    async def _run_initial_perception(self):
        p_input = build_perception_input(self.ctx.query, self.ctx.memory, self.ctx)
        log.info(f"📝 Initial Perception")
        logger_json_block(log,'Inital Perception input:', p_input)
        self.p_out = await self.perception.run(p_input, self.ctx)
        log.info(f"📝 Initial Perception output")
        logger_json_block(log,'Initial Perception output:', self.p_out)

        self.ctx.mark_step_completed(StepType.ROOT)
        self.ctx.attach_perception(StepType.ROOT, self.p_out)

        log_json_block('📌 Browser Agent Perception output (ROOT)', self.p_out)
        self.ctx._print_graph(depth=2, title="Browser Agent", color="green")

    async def _plan_next_steps(self, query: str) -> Dict[str, Any]:
        """Plan the next steps for browser operation
        
        Args:
            query: The user's query
            
        Returns:
            Dict containing the plan
        """
        log.info("Planning browser operation steps...")
        d_input = build_browser_decision_input(self.ctx, query, self.p_out, plan_mode="initial")
        log.info(f"Decision input:")
        logger_json_block(log,'Decision input:', d_input)
        plan = await self.decision.run(d_input)
        log.info(f"Decision output:")
        logger_json_block(log,'Decision output:', plan)
        log_json_block(f"📌 Browser Agent Decision output (initial)", plan)
        log.info(f"Planned {len(plan['plan_graph']['nodes'])} steps")
        log.info(f"📋 Planned steps: {json.dumps(plan, indent=2)}")
        
        # Add steps to context
        for node in plan["plan_graph"]["nodes"]:
            self.ctx.add_step(
                step_id=node["id"],
                description=node["description"],
                step_type=StepType.BROWSEROPERATION,
                from_step=node["from"] if "from" in node else None
            )
        
        # Then add edges according to the plan
        for edge in plan["plan_graph"]["edges"]:
            self.ctx.graph.add_edge(edge["from"], edge["to"])
        
        # Store plan details
        self.code_variants = plan["code_variants"]
        self.next_step_id = plan["next_step_id"]

        self.ctx._print_graph(depth=3, title="Browser Agent", color="green")
        
        return plan

    async def _execute_steps(self, plan: Dict[str, Any]) -> bool:
        """Execute the planned steps
        
        Args:
            plan: The plan containing steps to execute
            
        Returns:
            bool: True if all steps completed successfully, False otherwise
        """
        tracker = StepExecutionTracker(max_steps=12, max_retries=5)
        AUTO_EXECUTION_MODE = "fallback"

        while tracker.should_continue():
            tracker.increment()
            log.info(f"🔁 Browser Agent Loop {tracker.tries} — Executing step {self.next_step_id}")
            log_step(f"🔁 Browser Agent - Loop {tracker.tries} — Executing step {self.next_step_id}")

            if self.ctx.is_step_completed(self.next_step_id):
                log.info(f"✅ Step {self.next_step_id} already completed. Skipping.")
                self.next_step_id = self._pick_next_step(self.ctx)
                continue

            retry_step_id = tracker.retry_step_id(self.next_step_id)
            log.info(f"🔍 Executing step {retry_step_id}")
            success = await execute_step_with_mode(
                retry_step_id,
                self.code_variants,
                self.ctx,
                AUTO_EXECUTION_MODE,
                None,  # No session needed for browser operations
                self.multi_mcp
            )

            #if not success:
            if success.get("status") != "success": 
                log.error(f"❌ Step {retry_step_id} failed. Marking as failed.")
                self.ctx.mark_step_failed(self.next_step_id, "All fallback variants failed")
                tracker.record_failure(self.next_step_id)

                if tracker.has_exceeded_retries(self.next_step_id):
                    if self.next_step_id == StepType.ROOT:
                        if tracker.register_root_failure():
                            log.error("🚨 ROOT failed too many times. Halting execution.")
                            log_error("🚨 ROOT failed too many times. Halting execution.")
                            return False
                    else:
                        log.error(f"⚠️ Step {self.next_step_id} failed too many times. Forcing replan.")
                        log_error(f"⚠️ Step {self.next_step_id} failed too many times. Forcing replan.")
                        self.next_step_id = StepType.ROOT
                    continue

            self.ctx.mark_step_completed(self.next_step_id)
            log.info(f"✅ Step {self.next_step_id} completed successfully.")

            # 🔍 Perception after execution
            p_input = build_perception_input(self.ctx.query, self.ctx.memory, self.ctx, snapshot_type="step_result")
            log.info(f"Perception input:")
            logger_json_block(log,'Perception input:', p_input)
            self.p_out = await self.perception.run(p_input, self.ctx)
            log.info(f"Perception output:")
            logger_json_block(log,'Perception output:', self.p_out)
            self.ctx.attach_perception(self.next_step_id, self.p_out)
            log_json_block(f"📌 Browser Agent Perception output ({self.next_step_id})", self.p_out)
            self.ctx._print_graph(depth=3, title="Browser Agent", color="green")

            if self.p_out.get("original_goal_achieved") or self.p_out.get("route") == Route.SUMMARIZE:
                log.info(f"✅✅ Original goal achieved or route is summarize, Now concluding...")
                log_step(f"✅✅ Original goal achieved or route is summarize, Now concluding...")
                return True

            if self.p_out.get("route") != Route.BROWSER:
                log.error("🚩 Invalid route from perception. Exiting.")
                log_error("🚩 Invalid route from perception. Exiting.")
                return False

            # 🔁 Decision again
            log.info(f"🔁 Browser Agent - Running Decision again")
            d_input = build_browser_decision_input(self.ctx, self.ctx.query, self.p_out, plan_mode="mid-session")
            log.info(f"Decision input:")
            logger_json_block(log,'Decision input:', d_input)
            d_out = await self.decision.run(d_input)
            log.info(f"Decision output:")
            logger_json_block(log,'Decision output:', d_out)
            log_json_block(f"📌 Browser Agent Decision output ({tracker.tries})", d_out)

            self.next_step_id = d_out["next_step_id"]
            self.code_variants = d_out["code_variants"]
            plan_graph = d_out["plan_graph"]
            self.update_plan_graph(self.ctx, plan_graph, self.next_step_id)
            self.ctx._print_graph(depth=3, title="Browser Agent", color="green")

        return True

    def _pick_next_step(self, ctx) -> str:
        """Pick the next uncompleted step from the graph"""
        for node_id in ctx.graph.nodes:
            node = ctx.graph.nodes[node_id]["data"]
            if node.status == "pending":
                return node.index
        return StepType.ROOT

    def update_plan_graph(self, ctx, plan_graph, from_step_id):
        """Update the plan graph with new nodes and edges"""
        for node in plan_graph["nodes"]:
            step_id = node["id"]
            if step_id in ctx.graph.nodes:
                existing = ctx.graph.nodes[step_id]["data"]
                if existing.status != "pending":
                    continue
            ctx.add_step(step_id, description=node["description"], step_type=StepType.BROWSEROPERATION)
        
        for edge in plan_graph["edges"]:
            if edge["from"] in ctx.graph.nodes and edge["to"] in ctx.graph.nodes:
                ctx.graph.add_edge(edge["from"], edge["to"], type=edge.get("type", "normal"))

class StepExecutionTracker:
    def __init__(self, max_steps=12, max_retries=3):
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.attempts = {}
        self.tries = 0
        self.root_failures = 0

    def increment(self):
        self.tries += 1

    def record_failure(self, step_id):
        self.attempts[step_id] = self.attempts.get(step_id, 0) + 1

    def retry_step_id(self, step_id):
        attempts = self.attempts.get(step_id, 0)
        return f"{step_id}F{attempts}" if attempts > 0 else step_id

    def should_continue(self):
        return self.tries < self.max_steps

    def has_exceeded_retries(self, step_id):
        log.info(f"Attempts for step {step_id}: {self.attempts.get(step_id, 0)} attempts and max retries are {self.max_retries}")
        return self.attempts.get(step_id, 0) >= self.max_retries

    def register_root_failure(self):
        self.root_failures += 1
        return self.root_failures >= 2