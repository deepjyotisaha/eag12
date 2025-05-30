# browser_agent_summarize.py
import os
import json
from pathlib import Path
from utils.utils import log_step, log_error, log_json_block
from google.genai.errors import ServerError
import time
from typing import Any, Optional
from datetime import datetime
from agent.model_manager import ModelManager
from config.log_config import setup_logging, logger_json_block

log = setup_logging(__name__)

class BrowserAgentSummarizer:
    def __init__(self, summarizer_prompt_path: str, api_key: str | None = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment or explicitly provided.")
        self.model = ModelManager()
        
        # Convert to absolute path
        base_dir = Path(__file__).parent.parent  # Get browser_agent directory
        self.summarizer_prompt_path = str(base_dir / summarizer_prompt_path)
        
        # Verify prompt file exists
        if not Path(self.summarizer_prompt_path).exists():
            raise FileNotFoundError(f"Browser summarizer prompt file not found: {self.summarizer_prompt_path}")

    async def run(self, s_input: dict) -> str:
        try:
            # Read prompt with explicit encoding
            with open(self.summarizer_prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
                
            if not prompt_template:
                raise ValueError(f"Browser summarizer prompt file is empty: {self.summarizer_prompt_path}")

            full_prompt = (
                f"Current Time: {datetime.utcnow().isoformat()}\n\n"
                f"{prompt_template.strip()}\n\n"
                f"{json.dumps(s_input, indent=2)}"
            )

            log_step("[SENDING PROMPT TO BROWSER SUMMARIZER...]")
            time.sleep(2)
            response = await self.model.generate_text(
                prompt=full_prompt
            )
            return response
        except FileNotFoundError as e:
            log_error(f"Browser summarizer prompt file not found: {e}")
            return "Browser operation summary unavailable due to missing prompt file."
        except ValueError as e:
            log_error(f"Browser summarizer prompt file error: {e}")
            return "Browser operation summary unavailable due to invalid prompt file."
        except ServerError as e:
            log_error(f"Browser summarizer LLM ServerError: {e}")
            return "Browser operation summary unavailable due to model error (503)."
        except Exception as e:
            log_error(f"Unexpected browser summarizer error: {e}")
            return "Browser operation summary generation failed due to internal error."

    async def summarize(self, query: str, ctx, latest_perception: dict) -> dict:
        """Summarize browser operations and create final plan
        
        Args:
            query: Original query
            ctx: Browser context
            latest_perception: Latest perception output
            
        Returns:
            dict: Final plan with summary
        """
        # Mark all remaining pending steps as "Skipped"
        for node_id in ctx.graph.nodes:
            node = ctx.graph.nodes[node_id]["data"]
            if node.status == "pending":
                node.status = "Skipped"

        s_input = {
            "original_query": query,
            "globals_schema": ctx.globals,
            "plan_graph": ctx.get_context_snapshot()["graph"],
            "perception": latest_perception
        }

        summary = await self.run(s_input)
        
        # Create final plan
        final_plan = {
            "context": ctx.get_context_snapshot(),
            "status": "success",
            "final_step_id": ctx.get_latest_node(),
            "reason": "Browser operation summarized successfully",
            "timestamp": datetime.utcnow().isoformat(),
            "original_query": ctx.query,
            "final_summary": summary,
            "browser_operation": True  # Flag to identify this as a browser operation result
        }

        logger_json_block(log, "Final plan", final_plan)

        return final_plan