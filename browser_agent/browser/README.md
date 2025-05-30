# Browser Agent

A specialized agent for web browser automation and interaction, built on top of the MCP (Multi-Component Protocol) framework.

## Overview

The Browser Agent is designed to handle web browser automation tasks through a structured approach using perception, decision-making, and execution components. It can navigate websites, interact with elements, fill forms, and perform other browser-based operations.

## Components

### Core Components

- **BrowserAgent**: Main orchestrator that manages the browser automation workflow
- **BrowserContext**: Manages the state and execution graph of browser operations
- **BrowserPerception**: Analyzes browser state and user queries
- **BrowserDecision**: Plans browser operations and generates execution steps
- **BrowserAgentSummarizer**: Creates summaries of completed browser operations

### Supporting Components

- **StepExecutionTracker**: Tracks step execution progress and retries
- **MultiMCP**: Manages browser-specific MCP tools and operations

## Features

- Web page navigation
- Form filling and submission
- Element interaction (clicks, inputs)
- Dynamic page state tracking
- Error handling and retry mechanisms
- Operation summarization

## Usage

```python
from browser_agent import BrowserAgent
from mcp_servers.multiMCP import MultiMCP

# Initialize the agent
agent = BrowserAgent(multi_mcp)

# Run a browser operation
result = await agent.run("Navigate to example.com and fill the login form")
```

## Configuration

The agent requires a `mcp_server_config.yaml` file with browser server configuration:

```yaml
mcp_servers:
  - id: "webbrowsing"
    script: "path/to/browser_mcp_server.py"
    cwd: "path/to/working/directory"
```

## Error Handling

The agent includes comprehensive error handling:
- Step execution failures
- Browser state validation
- Tool execution errors
- Network issues

## Logging

Detailed logging is available for:
- Step execution
- Browser state changes
- Tool operations
- Error conditions

## Dependencies

- MCP Framework
- Playwright (for browser automation)
- NetworkX (for execution graph)
- PyYAML (for configuration)

## File Structure

```
browser_agent/
├── browser/
│   ├── browser_agent.py
│   ├── browser_context.py
│   ├── browser_perception.py
│   ├── browser_decision.py
│   └── browser_summarize.py
├── config/
│   └── mcp_server_config.yaml
└── prompts/
    ├── browser_agent_perception_prompt.txt
    ├── browser_agent_decision_prompt.txt
    └── browser_agent_summarizer_prompt.txt
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]