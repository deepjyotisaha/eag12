import os
import json
from pathlib import Path
from utils.utils import log_step, log_error, log_json_block
from config.log_config import setup_logging, logger_prompt
from browser.browser_decision import BrowserDecision, build_browser_decision_input
from browser.browser_action import BrowserAction
from action.execute_step import execute_step_with_mode
from agent.agentSession import AgentSession
from agent.contextManager import ContextManager
from mcp_servers.multiMCP import MultiMCP
from agent.model_manager import ModelManager
import uuid
from datetime import datetime

log = setup_logging(__name__)

class BrowserAgent:
    def __init__(self, browser_decision_prompt_path: str, multi_mcp: MultiMCP, model: ModelManager):
        """
        Initialize the browser agent with browser-specific decision and action components.
        """
        browser_decision_prompt_path = "prompts/browser_decision_prompt.txt"
        
        self.decision = BrowserDecision(browser_decision_prompt_path, multi_mcp, model=model)
        self.action = BrowserAction()
        self.multi_mcp = multi_mcp
        self.model = model

    async def run(self, query: str, ctx: ContextManager, session: AgentSession) -> bool:
        """
        Execute browser-specific decision and action steps.
        Called by AgentLoop after perception and early exit checks.
        
        Args:
            query: The user's query
            ctx: The context manager instance
            session: The agent session instance
            
        Returns:
            bool: True if browser operations completed successfully, False otherwise
        """
        try:
            # Build decision input using the context
            d_input = build_browser_decision_input(
                ctx=ctx,
                query=query,
                p_out=ctx.get_latest_perception(),
                strategy="exploratory"
            )

            # Get decision from browser-specific decision module
            log_step("[SENDING PROMPT TO BROWSER DECISION...]", symbol="→")
            d_out = await self.decision.run(d_input, session=session)
            log_step("[RECEIVED OUTPUT FROM BROWSER DECISION...]", symbol="←")

            if "error" in d_out:
                log_error(f"Browser decision failed: {d_out['error']}")
                return False

            # Add steps to context
            for node in d_out["plan_graph"]["nodes"]:
                ctx.add_step(
                    step_id=node["id"],
                    description=node["description"],
                    step_type="CODE",
                    from_node="ROOT"
                )

            # Execute steps using browser-specific action
            next_step_id = d_out["next_step_id"]
            code_variants = d_out["code_variants"]
            max_retries = 5
            retry_count = 0

            while retry_count < max_retries:
                if ctx.is_step_completed(next_step_id):
                    next_step_id = ctx._pick_next_step()
                    continue

                # Execute the current step using execute_step_with_mode
                result = await execute_step_with_mode(
                    step_id=next_step_id,
                    code_variants=code_variants,
                    ctx=ctx,
                    mode="fallback",  # Using fallback mode for browser actions
                    session=session,
                    multi_mcp=self.multi_mcp
                )

                if result.get("status") == "success":
                    ctx.mark_step_completed(next_step_id)
                    return True
                else:
                    ctx.mark_step_failed(next_step_id, result.get("error", "Browser action failed"))
                    retry_count += 1

                    if retry_count >= max_retries:
                        log_error(f"Browser action failed after {max_retries} retries")
                        return False

            return False

        except Exception as e:
            log_error(f"Browser agent error: {str(e)}")
            return False 