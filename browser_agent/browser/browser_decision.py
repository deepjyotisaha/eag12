# browser/browser_decision.py
from typing import Dict, Any
from agent.model_manager import ModelManager
from utils.json_parser import parse_llm_json
from config.log_config import setup_logging, logger_prompt
from pathlib import Path
import json
from datetime import datetime

log = setup_logging(__name__)

def build_browser_decision_input(ctx, query, p_out, plan_mode: str = "initial") -> Dict[str, Any]:
    """Build input for browser decision
    
    Args:
        ctx: BrowserContext instance
        query: The user's query
        p_out: Perception output
        plan_mode: Either "initial" for first planning or "mid-session" for replanning
        
    Returns:
        Dict containing the input for decision
    """
    return {
        "current_time": datetime.utcnow().isoformat(),
        "plan_mode": plan_mode,  # "initial" or "mid-session"
        "planning_strategy": "browser",
        "original_query": query,
        "perception": p_out,
        "plan_graph": {},  # initially empty
        "completed_steps": [ctx.graph.nodes[n]["data"].__dict__ for n in ctx.graph.nodes if ctx.graph.nodes[n]["data"].status == "completed"],
        "failed_steps": [ctx.graph.nodes[n]["data"].__dict__ for n in ctx.failed_nodes],
        "globals_schema": {
            k: {
                "type": type(v).__name__,
                "preview": str(v)[:500] + ("…" if len(str(v)) > 500 else "")
            } for k, v in ctx.globals.items()
        }
    }

class BrowserDecision:
    def __init__(self, decision_prompt_path: str, multi_mcp):
        self.decision_prompt_path = decision_prompt_path
        self.multi_mcp = multi_mcp
        self.model = ModelManager()

    async def run(self, decision_input: dict) -> Dict[str, Any]:
        """Plan browser operations using LLM
        
        Args:
            decision_input: Dictionary containing the input for decision
            
        Returns:
            Dict containing the plan
        """
        try:
            # Read prompt template and get tool descriptions
            prompt_template = Path(self.decision_prompt_path).read_text(encoding="utf-8")
            function_list_text = self.multi_mcp.tool_description_wrapper()
            tool_descriptions = "\n".join(f"- `{desc.strip()}`" for desc in function_list_text)
            tool_descriptions = "\n\n### The ONLY Available Tools\n\n---\n\n" + tool_descriptions
            
            # Format the full prompt
            full_prompt = f"{prompt_template.strip()}\n{tool_descriptions}\n\n```json\n{json.dumps(decision_input, indent=2)}\n```"
            
            #log.info(f"Decision input: {decision_input}")

            logger_prompt(log, "📝 Browser Agent Decision prompt:", full_prompt)
            
            # Generate the plan
            response = await self.model.generate_text(full_prompt)
            #log.info(f"Model response: {response}")
            
            # Parse and validate the plan
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
            log.error(f"Error planning steps: {e}")
            raise