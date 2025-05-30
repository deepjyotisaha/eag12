import asyncio
import yaml
from pathlib import Path
import sys
import json

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from browser_agent import BrowserAgent
from mcp_servers.multiMCP import MultiMCP
from dotenv import load_dotenv
from config.log_config import setup_logging
from utils.utils import log_error

log = setup_logging(__name__)


async def main():
    multi_mcp = None  # Initialize outside try block for proper cleanup
    try:
        # Load environment variables
        log.info("Loading environment variables...")
        load_dotenv()
        
        # Load MCP server configs
        log.info("Loading MCP server configurations...")
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
        multi_mcp = MultiMCP(server_configs=[browser_config])
        await multi_mcp.initialize()
        
        # Log available tools and their details
        tools = await multi_mcp.list_all_tools()
        log.info(f"Successfully initialized MultiMCP with {len(tools)} tools")
        
        # Log tool descriptions in the same format as decision prompt
        log.info("\n=== Available Tools ===")
        function_list_text = multi_mcp.tool_description_wrapper()
        tool_descriptions = "\n".join(f"- `{desc.strip()}`" for desc in function_list_text)
        log.info("\n" + tool_descriptions)
        
        # Initialize browser agent
        log.info("Initializing BrowserAgent...")
        agent = BrowserAgent(multi_mcp)
        log.info("BrowserAgent initialized successfully")
        
        while True:
            query = input("\nEnter your browser query (or 'exit' to quit): ")
            if query.lower() == 'exit':
                log.info("Exiting browser agent...")
                break
                
            log.info(f"Processing query: {query}")
            result = await agent.run(query)
            log.info(f"Query result: {result}")
            print(f"\nResult: {result}")
            
    except Exception as e:
        log_error("Fatal error in browser agent", e)
        raise
    finally:
        if multi_mcp:  # Only shutdown if multi_mcp was initialized
            log.info("Shutting down MultiMCP...")
            await multi_mcp.shutdown()
            log.info("MultiMCP shutdown complete")




if __name__ == "__main__":
    asyncio.run(main())
