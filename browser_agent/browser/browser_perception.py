import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from agent.model_manager import ModelManager
from utils.utils import log_step, log_error, log_json_block
from utils.json_parser import parse_llm_json
from config.log_config import setup_logging, logger_prompt
from browser.browser_context import BrowserContext

log = setup_logging(__name__)

class BrowserPerception:
    def __init__(self, perception_prompt_path: str, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        """Initialize browser perception with prompt template"""
        self.perception_prompt_path = perception_prompt_path
        self.model = ModelManager()

    async def run(self, p_input: dict, ctx: BrowserContext) -> dict:
        """Run perception on browser query"""
        # Read and format prompt
        prompt_template = Path(self.perception_prompt_path).read_text(encoding="utf-8")
        full_prompt = (
            f"{prompt_template.strip()}\n\n"
            "```json\n"
            f"{json.dumps(p_input, indent=2)}\n"
            "```"
        )

        logger_prompt(log, "📝 Browser perception prompt:", full_prompt)

        try:
            log_step("[SENDING PROMPT TO BROWSER PERCEPTION...]", symbol="→")
            response = await self.model.generate_text(prompt=full_prompt)
            log_step("[RECEIVED OUTPUT FROM BROWSER PERCEPTION...]", symbol="←")

            # Parse and validate response
            output = parse_llm_json(response, required_keys=[
                'entities',
                'result_requirement',
                'original_goal_achieved',
                'reasoning',
                'local_goal_achieved',
                'local_reasoning',
                'last_tooluse_summary',
                'solution_summary',
                'confidence',
                'current_browser_state',
                'route'
            ])

            return output

        except Exception as e:
            log_error("🛑 EXCEPTION IN BROWSER PERCEPTION:", e)
            # Fallback output
            return {
                "entities": [],
                "result_requirement": "N/A",
                "original_goal_achieved": False,
                "reasoning": "Browser perception failed to parse model output.",
                "local_goal_achieved": False,
                "local_reasoning": "Could not extract structured information.",
                "last_tooluse_summary": "None",
                "solution_summary": "Not ready yet",
                "confidence": "0.0",
                "current_browser_state": "Cannot determine current browser state",
                "route": "browser"
            }

def build_browser_perception_input(query: str, ctx: BrowserContext, snapshot_type: str) -> dict:
    """Build input for browser perception
    
    Args:
        query: The user's query
        ctx: Browser context
        snapshot_type: Type of snapshot (e.g., "browser_query", "step_result")
    """
    return {
        "current_time": datetime.utcnow().isoformat(),
        "run_id": f"{ctx.session_id}-BP",
        "snapshot_type": snapshot_type,  # Use the passed snapshot type
        "original_query": query,
        "raw_input": query if snapshot_type == "browser_query" else str(ctx.globals),
        "current_plan": getattr(ctx, "plan_graph", {}),
        "completed_steps": [ctx.graph.nodes[n]["data"].__dict__ for n in ctx.graph.nodes if ctx.graph.nodes[n]["data"].status == "completed"],
        "failed_steps": [ctx.graph.nodes[n]["data"].__dict__ for n in ctx.failed_nodes],
        "globals_schema": {
            k: (type(v).__name__, str(v)[:120]) for k, v in ctx.globals.items()
        },
        "current_browser_state": ctx.current_browser_state,
        "timestamp": "...",
        "schema_version": 1
    }