# EAG12 - Intelligent Agent System

A sophisticated agent system built on the MCP (Multi-Component Protocol) framework, featuring a main agent (S12) and a specialized browser agent for web automation.

## Overview

The EAG12 system consists of two main components:

1. **Main Agent (S12)**: A general-purpose agent capable of understanding and executing complex tasks
2. **Browser Agent**: A specialized agent for web browser automation and interaction

## System Architecture

### Main Agent (S12)

The main agent serves as the central orchestrator of the system, with the following responsibilities:

- Task understanding and planning
- State management and memory
- Action execution and monitoring
- Task summarization and reporting

#### Core Components

```
S12/
├── agent/             # Core agent implementation
├── perception/        # Task and environment analysis
├── decision/          # Action planning and decision making
├── action/            # Task execution
├── memory/            # State and history management
├── summarization/     # Operation summarization
├── mcp_servers/       # MCP server implementations
├── browserMCP/        # Browser-specific tools
├── utils/             # Utility functions
├── prompts/           # Agent prompts
├── config/            # Configuration files
├── heuristics/        # Decision rules
└── media/             # Media handling
```

### Browser Agent

The browser agent specializes in web automation tasks:

- Web page navigation
- Form interaction
- Element manipulation
- State tracking
- Error handling

#### Core Components

```
browser_agent/
├── browser/           # Browser automation core
├── agent/             # Agent implementation
├── perception/        # Web page analysis
├── decision/          # Browser operation planning
├── action/            # Browser action execution
├── memory/            # Browser state tracking
├── summarization/     # Operation summaries
├── mcp_servers/       # Browser MCP servers
├── browserMCP/        # Browser-specific tools
├── utils/             # Utility functions
├── prompts/           # Agent prompts
├── config/            # Configuration
├── heuristics/        # Browser-specific rules
└── media/             # Media handling
```

## Getting Started

### Prerequisites

- Python 3.8+
- MCP Framework
- Playwright (for browser automation)
- NetworkX (for execution graphs)
- PyYAML (for configuration)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Both agents require configuration files in their respective `config/` directories:

- `mcp_server_config.yaml`: MCP server settings
- `agent_config.yaml`: Agent-specific configurations
- `prompts/`: Agent prompt templates

### Usage

#### Main Agent

```python
from S12.main import run_agent

# Run a task
result = await run_agent("Your task description")
```

#### Browser Agent

```python
from browser_agent.main import run_browser_agent

# Run a browser task
result = await run_browser_agent("Navigate to example.com and fill the form")
```

## Development

### Project Structure

```
eag12/
├── S12/              # Main agent
├── browser_agent/    # Browser agent
├── config/           # Global configuration
└── docs/            # Documentation
```

### Key Features

- **Modular Design**: Each component is independently maintainable
- **Extensible**: Easy to add new capabilities
- **Robust Error Handling**: Comprehensive error management
- **State Management**: Persistent state tracking
- **Logging**: Detailed operation logging

## Queries

1. Find the ASCII values of characters in INDIA and then return sum of exponentials of those values.
2. How much Anmol singh paid for his DLF apartment via Capbridge? 
3. What do you know about Don Tapscott and Anthony Williams?
4. What is the relationship between Gensol and Go-Auto?
5. which course are we teaching on Canvas LMS? "H:\DownloadsH\How to use Canvas LMS.pdf"
6. Summarize this page: https://theschoolof.ai/
7. What is the log value of the amount that Anmol singh paid for his DLF apartment via Capbridge? Hint: use local 
8. find the the main difference between latest BMW 7 and 5 series online. Reply back in detail and in markdown.
9. How much money did Anmol Singh paid to DLF to buy an apartment in Camelias indirectly? Search local storage agian?
10. What are the main differences between Mercedes S Class end E Class. Reply back in markdown list. 
11. Who is the current chairman of DLF? Search local documents. 

### Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your license information here]



