from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import networkx as nx
from datetime import datetime

@dataclass
class BrowserStateNode:
    url: str
    title: str
    type: str  # PAGE, NAVIGATION, INTERACTION
    status: str = "pending"  # pending, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = datetime.utcnow().isoformat()
    from_state: Optional[str] = None  # for tracking state transitions

class BrowserContextManager:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state_graph = nx.DiGraph()
        self.completed_states: List[str] = []
        self.failed_states: List[str] = []
        self.latest_state_id: Optional[str] = None
        self.globals: Dict[str, Any] = {}  # For storing browser-related global state

        # Initialize root state
        root_state = BrowserStateNode(
            url="about:blank",
            title="Initial State",
            type="ROOT",
            status="completed"
        )
        self.state_graph.add_node("ROOT", data=root_state)


    def add_state(self, state_id: str, url: str, title: str, state_type: str, 
                 from_state: Optional[str] = None, edge_type: str = "normal") -> str:
        """Add a new browser state to the graph"""
        state_node = BrowserStateNode(
            url=url,
            title=title,
            type=state_type,
            from_state=from_state
        )
        self.state_graph.add_node(state_id, data=state_node)
        if from_state:
            self.state_graph.add_edge(from_state, state_id, type=edge_type)
        self.latest_state_id = state_id
        return state_id

    def mark_state_completed(self, state_id: str, result: Optional[Dict[str, Any]] = None):
        """Mark a browser state as completed with optional result"""
        if state_id in self.state_graph:
            node: BrowserStateNode = self.state_graph.nodes[state_id]["data"]
            node.status = "completed"
            if result:
                node.result = result
                self._update_globals(result)

    def mark_state_failed(self, state_id: str, error_msg: str):
        """Mark a browser state as failed with error message"""
        node: BrowserStateNode = self.state_graph.nodes[state_id]["data"]
        node.status = "failed"
        node.error = error_msg
        self.failed_states.append(state_id)

    def get_current_state(self) -> Optional[BrowserStateNode]:
        """Get the current browser state"""
        if self.latest_state_id:
            return self.state_graph.nodes[self.latest_state_id]["data"]
        return None

    def get_state_history(self) -> List[BrowserStateNode]:
        """Get the history of browser states"""
        return [
            self.state_graph.nodes[node]["data"]
            for node in nx.topological_sort(self.state_graph)
        ]

    def _update_globals(self, new_vars: Dict[str, Any]):
        """Update global browser state"""
        for k, v in new_vars.items():
            if k in self.globals:
                versioned_key = f"{k}__{self.latest_state_id}"
                self.globals[versioned_key] = v
            else:
                self.globals[k] = v

    def get_context_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the current browser context"""
        def serialize_node_data(data):
            if hasattr(data, '__dict__'):
                return data.__dict__
            return data

        graph_data = nx.readwrite.json_graph.node_link_data(self.state_graph, edges="links")
        for node in graph_data["nodes"]:
            if "data" in node:
                node["data"] = serialize_node_data(node["data"])

        return {
            "session_id": self.session_id,
            "browser_profile": self.browser_profile.model_dump() if self.browser_profile else None,
            "globals": self.globals,
            "state_graph": graph_data,
            "failed_states": self.failed_states,
            "latest_state": self.latest_state_id
        }

    async def cleanup(self):
        """Clean up browser resources"""
        if self.browser_session:
            await self.browser_session.stop()
