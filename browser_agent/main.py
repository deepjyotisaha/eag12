from utils.utils import log_step, log_error
import asyncio
import yaml
from dotenv import load_dotenv
from mcp_servers.multiMCP import MultiMCP
from agent.agent_loop3 import AgentLoop  # 🆕 Use loop3
from pprint import pprint
from config.log_config import setup_logging

log = setup_logging(__name__)

BANNER = """
──────────────────────────────────────────────────────
🔸  Agentic Query Assistant  🔸
Type your question and press Enter.
Type 'exit' or 'quit' to leave.
──────────────────────────────────────────────────────
"""

async def interactive() -> None:
    log_step(BANNER, symbol="")
    log_step('Loading MCP Servers...', symbol="📥")

    # Load MCP server configs
    with open("config/mcp_server_config.yaml", "r") as f:
        profile = yaml.safe_load(f)
        mcp_servers_list = profile.get("mcp_servers", [])
        configs = list(mcp_servers_list)
    # Load profiles config
    with open("config/profiles.yaml", "r") as f:
        profiles = yaml.safe_load(f)
        specialized_browser_agent_cfg = profiles.get("specialized_browser_agent", {})
        browser_agent_enabled = specialized_browser_agent_cfg.get("enabled", False)
        log.info(f"🟦 Specialized Browser agent is enabled: {browser_agent_enabled}")

        
    # Initialize MultiMCP dispatcher
    multi_mcp = MultiMCP(server_configs=configs)
    await multi_mcp.initialize()

    if browser_agent_enabled:
        log.info("🟦 Browser agent is enabled. Using browser perception prompt.")
        perception_prompt = "prompts/perception_prompt_browser.txt"
    else:
        log.info("🟦 Browser agent is disabled. Using default perception prompt.")
        perception_prompt = "prompts/perception_prompt.txt"

    # Create a single persistent AgentLoop instance
    loop = AgentLoop(
        perception_prompt=perception_prompt,
        decision_prompt="prompts/decision_prompt.txt",
        summarizer_prompt="prompts/summarizer_prompt.txt",
        multi_mcp=multi_mcp,
        strategy="exploratory",
        browser_agent_enabled=browser_agent_enabled
    )

    conversation_history = []  # stores (query, response) tuples

    try:
        while True:
            print("\n\n")
            query = input("📝  You: ").strip()
            if query.lower() in {"exit", "quit"}:
                log_step("Goodbye!", symbol="👋")
                break
            
            log.debug(f"📝 Query: {query}")

            # Construct context string from past rounds
            context_prefix = ""
            for idx, (q, r) in enumerate(conversation_history, start=1):
                context_prefix += f"Query {idx}: {q}\nResponse {idx}: {r}\n"

            log.debug(f"📝 Context Prefix: {context_prefix}")

            full_query = context_prefix + f"Query {len(conversation_history)+1}: {query}"

            log.debug(f"📝 Full Query: {full_query}")

            try:
                response = await loop.run(full_query)  # 🔄 stateless loop sees full pseudo-history
                conversation_history.append((query, response.strip()))
                log_step("Agent Resting now", symbol="😴")
            except Exception as e:
                if "Unknown SSE event" in str(e):
                    pass  # suppress event noise like ping
                else:
                    log_error("Agent failed", e)

            follow = input("Continue? (press Enter) or type 'exit': ").strip()
            if follow.lower() in {"exit", "quit"}:
                log_step("Goodbye!", symbol="👋")
                break
    finally:
        await multi_mcp.shutdown()

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(interactive())
