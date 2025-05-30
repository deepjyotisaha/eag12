from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
import networkx as nx
from utils.utils import log_step, log_error
import json
from datetime import datetime
from config.log_config import setup_logging, logger_prompt
from utils.utils import render_graph

log = setup_logging(__name__)

@dataclass
class BrowserStepNode:
    """Represents a step in the browser operation plan"""
    step_id: str
    description: str
    type: str = "BROWSEROPERATION"
    status: str = "pending"  # pending, completed, failed
    result: Optional[Dict[str, Any]] = None
    conclusion: Optional[str] = None
    error: Optional[str] = None
    perception: Optional[Dict[str, Any]] = None
    from_step: Optional[str] = None

@dataclass
class BrowserPerceptionResult:
    """Store perception results"""
    entities: list
    result_requirement: str
    original_goal_achieved: bool
    reasoning: str
    local_goal_achieved: bool
    local_reasoning: str
    last_tooluse_summary: str
    solution_summary: str
    confidence: str
    route: str


class BrowserContext:
    """Simplified context manager for browser operations"""
    def __init__(self, session_id: str, query: str):
        log.info(f"Initializing BrowserContext for session {session_id} with query: {query}")
        self.session_id = session_id
        self.query = query
        self.current_browser_state: Optional[Dict[str, Any]] = None
        self.failed_nodes: list[str] = []     # Node labels of failed steps
        self.globals: Dict[str, Any] = {}  # Store variables between steps
        self.graph = nx.DiGraph()
        self.latest_node_id = None  # Add this to track latest node
        self.memory: list[dict] = []
        
        log.info("Initializing BrowserContext, creating root node...")
        # Add root node
        root_node = BrowserStepNode(
            step_id="ROOT",
            type="ROOT",
            description=query,
            status="pending"
        )
        self.graph.add_node("ROOT", data=root_node)

    def get_latest_node(self) -> Optional[str]:
        """Get the ID of the latest node in the graph
        
        Returns:
            Optional[str]: ID of the latest node, or None if graph is empty
        """
        return self.latest_node_id

    def add_step(self, step_id: str, description: str, from_step: str = "ROOT", step_type: str = "browser"):
        """Add a step to the context
        
        Args:
            step_id: Unique identifier for the step
            description: Description of what the step does
            from_step: ID of the step this step follows from (default: "ROOT")
            step_type: Type of the step (default: "browser")
        """
        node = BrowserStepNode(
            step_id=step_id,
            type=step_type,
            description=description,
            from_step=from_step
        )
        self.graph.add_node(step_id, data=node)
        
        # Always add the edge if from_step is provided
        if from_step:
            self.graph.add_edge(from_step, step_id)
        
        self.latest_node_id = step_id
        return step_id

    def is_step_completed(self, step_id: str) -> bool:
        """Check if a step has been completed"""
        node = self.graph.nodes.get(step_id, {}).get("data")
        return node is not None and node.status == "completed"

    def update_step_result(self, step_id: str, result: dict):
        """Update step with execution result"""
        node: BrowserStepNode = self.graph.nodes[step_id]["data"]
        node.result = result
        node.status = "completed"
        self._update_globals(result)

    def mark_step_failed(self, step_id: str, error_msg: str):
        """Mark a step as failed"""
        node: BrowserStepNode = self.graph.nodes[step_id]["data"]
        node.status = "failed"
        node.error = error_msg

    def _update_globals(self, new_vars: Dict[str, Any]):
        """Update global variables with new values"""
        for k, v in new_vars.items():
            if k in self.globals:
                versioned_key = f"{k}__{self.latest_node_id}"
                self.globals[versioned_key] = v
            else:
                self.globals[k] = v

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the current context state"""
        def serialize_node_data(data):
            if hasattr(data, '__dict__'):
                return data.__dict__
            return data

        graph_data = nx.readwrite.json_graph.node_link_data(self.graph, edges="links")
        for node in graph_data["nodes"]:
            if "data" in node:
                node["data"] = serialize_node_data(node["data"])

        return {
            "session_id": self.session_id,
            "query": self.query,
            "globals": self.globals,
            "graph": graph_data
        }

    def attach_perception(self, step_id: str, perception: dict):
        """Attach perception result to a step"""
        if step_id not in self.graph.nodes:
            fallback_node = BrowserStepNode(
                step_id=step_id,
                description="Perception-only node",
                type="PERCEPTION"
            )
            self.graph.add_node(step_id, data=fallback_node)
        
        node: BrowserStepNode = self.graph.nodes[step_id]["data"]
        node.perception = perception
        
        # Handle failed steps based on local_goal_achieved
        if not perception.get("local_goal_achieved", True):
            self.failed_nodes.append(step_id)

    def mark_step_completed(self, step_id: str, result: Optional[Dict[str, Any]] = None):
        """Mark a step as completed and optionally store its result"""
        node: BrowserStepNode = self.graph.nodes[step_id]["data"]
        node.status = "completed"
        if result:
            node.result = result
            self._update_globals(result)

    def _print_graph(self, depth: int = 1, only_if: bool = True, title: str = "Browser Agent", color: str = "green"):
        """Print the execution graph for debugging"""
        if only_if:
            render_graph(self.graph, depth=depth, title=title, color=color)
