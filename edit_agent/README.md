# Edit Agent

A specialized agent for code editing and file manipulation, built on top of the MCP (Multi-Component Protocol) framework.

## Overview

The Edit Agent is designed to handle code editing tasks through a structured approach using perception, decision-making, and execution components. It can modify code files, create new files, and perform other code-related operations.

## Components

### Core Components

- **EditAgent**: Main orchestrator that manages the code editing workflow
- **EditContext**: Manages the state and execution graph of editing operations
- **EditPerception**: Analyzes code state and user queries
- **EditDecision**: Plans editing operations and generates execution steps
- **EditAgentSummarizer**: Creates summaries of completed editing operations

### Supporting Components

- **StepExecutionTracker**: Tracks step execution progress and retries
- **MultiMCP**: Manages edit-specific MCP tools and operations

## Features

- Code file modification
- New file creation
- Code analysis and understanding
- Syntax validation
- Error handling and retry mechanisms
- Operation summarization

## Usage

```python
from edit_agent import EditAgent
from mcp_servers.multiMCP import MultiMCP

# Initialize the agent
agent = EditAgent(multi_mcp)

# Run an editing operation
result = await agent.run("Add error handling to the login function in auth.py")
```

## Configuration

The agent requires a `mcp_server_config.yaml` file with edit server configuration:

```yaml
mcp_servers:
  - id: "editing"
    script: "path/to/edit_mcp_server.py"
    cwd: "path/to/working/directory"
```

## Error Handling

The agent includes comprehensive error handling:
- Syntax errors
- File access issues
- Code validation failures
- Tool execution errors

## Logging

Detailed logging is available for:
- Step execution
- Code state changes
- Tool operations
- Error conditions

## Dependencies

- MCP Framework
- AST (for code analysis)
- NetworkX (for execution graph)
- PyYAML (for configuration)

## File Structure

```
edit_agent/
├── edit/
│   ├── edit_agent.py
│   ├── edit_context.py
│   ├── edit_perception.py
│   ├── edit_decision.py
│   └── edit_summarize.py
├── config/
│   └── mcp_server_config.yaml
└── prompts/
    ├── edit_agent_perception_prompt.txt
    ├── edit_agent_decision_prompt.txt
    └── edit_agent_summarizer_prompt.txt
```

## Browser Agent Integration

The Edit Agent can work in conjunction with the Browser Agent for web-based code editing tasks. The Browser Agent provides:

1. **Web Navigation**: Access to web-based code repositories and documentation
2. **Form Interaction**: Ability to fill and submit code-related forms
3. **State Management**: Tracking of web page state for code editing operations
4. **Error Recovery**: Handling of web-specific errors during code editing

### Browser Agent Components

- **BrowserAgent**: Orchestrates web browser automation
- **BrowserContext**: Manages browser state and execution graph
- **BrowserPerception**: Analyzes web page state
- **BrowserDecision**: Plans browser operations
- **BrowserAgentSummarizer**: Creates summaries of browser operations

### Browser Agent Features

- Web page navigation
- Form filling and submission
- Element interaction
- Dynamic page state tracking
- Error handling and retries

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here] 