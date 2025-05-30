import uuid
from datetime import datetime

from perception.perception import Perception, build_perception_input
from decision.decision import Decision, build_decision_input
from summarization.summarizer import Summarizer
from agent.contextManager import ContextManager
from agent.agentSession import AgentSession
from memory.memory_search import MemorySearch
from action.execute_step import execute_step_with_mode
from utils.utils import log_step, log_error, save_final_plan, log_json_block
from config.log_config import setup_logging
from config.log_config import logger_json_block
from browser.browser_agent import BrowserAgent

log = setup_logging(__name__)

class Route:
    SUMMARIZE = "summarize"
    DECISION = "decision"
    BROWSER = "browser"

class StepType:
    ROOT = "ROOT"
    CODE = "CODE"


class AgentLoop:
    def __init__(self, perception_prompt, decision_prompt, summarizer_prompt, multi_mcp, strategy="exploratory", browser_agent_enabled=False):
        self.perception = Perception(perception_prompt)
        self.decision = Decision(decision_prompt, multi_mcp)
        self.summarizer = Summarizer(summarizer_prompt)
        self.multi_mcp = multi_mcp
        self.strategy = strategy
        self.status: str = "in_progress"
        self.browser_agent_enabled = browser_agent_enabled

    async def run(self, query: str):
        self._initialize_session(query)
        await self._run_initial_perception()

        if self._should_early_exit():
            log.info(f"⚡ Early exit condition met. Summarizing...")
            return await self._summarize()

        # ✅ Missing early exit guard added
        if self.p_out.get("route") != Route.DECISION and self.p_out.get("route") != Route.BROWSER:
            log.error(f"🚩 Invalid perception route. Exiting.")
            log_error("🚩 Invalid perception route. Exiting.")
            return "Summary generation failed."
        
        if self.browser_agent_enabled and self.p_out.get("route") == Route.BROWSER:
            if self.browser_agent_enabled:
                browser_agent = BrowserAgent()
                log.info("⚙️ Routing to BrowserAgent for browser-related query.")
                return await browser_agent.run(query, context=self.ctx)
            else:
                log.error("⚙️ Browser agent is not enabled. Cannot execute browser route.")
                return await self._handle_failure()

        if self.p_out.get("route") == Route.DECISION:
            log.info(f"⚙️ Routing to decision loop...")
            await self._run_decision_loop()

            if self.status == "success":
                log.info(f"✅ Successfully completed all steps. Returning final output...")
                return self.final_output

            log.error(f"❌ Failed to complete all steps. Handling failure...")
            return await self._handle_failure()

    def _initialize_session(self, query):
        self.session_id = str(uuid.uuid4())
        self.ctx = ContextManager(self.session_id, query)
        self.session = AgentSession(self.session_id, query)
        self.query = query
        #self.memory = MemorySearch().search_memory(query)
        self.memory = None
        log.debug(f"📝 Memory: {self.memory}")
        log.warning(f"⚠️ WARNING: MemorySearch has been disabled from code!! Enable it to use memory.")
        self.ctx.globals = {"memory": self.memory}

    async def _run_initial_perception(self):
        p_input = build_perception_input(self.query, self.memory, self.ctx)
        log.info(f"📝 Initial Perception")
        logger_json_block(log,'Inital Perception input:', p_input)
        self.p_out = await self.perception.run(p_input, session=self.session)
        log.info(f"📝 Initial Perception output")
        logger_json_block(log,'Initial Perception output:', self.p_out)

        # This is not needed, because the root node is created in the BrowserContext constructor
        #self.ctx.add_step(step_id=StepType.ROOT, description="initial query", step_type=StepType.ROOT)
        self.ctx.mark_step_completed(StepType.ROOT)
        self.ctx.attach_perception(StepType.ROOT, self.p_out)

        log_json_block('📌 Perception output (ROOT)', self.p_out)
        self.ctx._print_graph(depth=2)

    def _should_early_exit(self) -> bool:
        return (
            self.p_out.get("original_goal_achieved") or
            self.p_out.get("route") == Route.SUMMARIZE
        )

    async def _summarize(self):
        return await self.summarizer.summarize(self.query, self.ctx, self.p_out, self.session)

    async def _run_decision_loop(self):
        """Executes initial decision and begins step execution."""
        d_input = build_decision_input(self.ctx, self.query, self.p_out, self.strategy)
        log.info(f"📌 Decision input")
        logger_json_block(log,'📌 Decision input:', d_input)
        d_out = await self.decision.run(d_input, session=self.session)
        log.info(f"📌 Decision output")
        logger_json_block(log,'📌 Decision output:', d_out)
        log_json_block("📌 Decision Output", d_out)

        self.code_variants = d_out["code_variants"]
        self.next_step_id = d_out["next_step_id"]

        for node in d_out["plan_graph"]["nodes"]:
            self.ctx.add_step(
                step_id=node["id"],
                description=node["description"],
                step_type=StepType.CODE
            )

        for edge in d_out["plan_graph"]["edges"]:
            self.ctx.graph.add_edge(edge["from"], edge["to"], type=edge.get("type", "normal"))

        await self._execute_steps_loop()

    async def _execute_steps_loop(self):
        tracker = StepExecutionTracker(max_steps=12, max_retries=5)
        AUTO_EXECUTION_MODE = "fallback"

        while tracker.should_continue():
            tracker.increment()
            log.info(f"🔁 Loop {tracker.tries} — Executing step {self.next_step_id}")
            log_step(f"🔁 Loop {tracker.tries} — Executing step {self.next_step_id}")

            if self.ctx.is_step_completed(self.next_step_id):
                log.info(f"✅ Step {self.next_step_id} already completed. Skipping.")
                log_step(f"✅ Step {self.next_step_id} already completed. Skipping.")
                self.next_step_id = self._pick_next_step(self.ctx)
                log.info(f"🔍 Next step: {self.next_step_id}")
                continue

            retry_step_id = tracker.retry_step_id(self.next_step_id)
            log.info(f"🔍 Executing step {retry_step_id}")
            success = await execute_step_with_mode(
                retry_step_id,
                self.code_variants,
                self.ctx,
                AUTO_EXECUTION_MODE,
                self.session,
                self.multi_mcp
            )

            if not success:
                log.error(f"❌ Step {retry_step_id} failed. Marking as failed.")
                self.ctx.mark_step_failed(self.next_step_id, "All fallback variants failed")
                tracker.record_failure(self.next_step_id)

                if tracker.has_exceeded_retries(self.next_step_id):
                    if self.next_step_id == StepType.ROOT:
                        if tracker.register_root_failure():
                            log.error("🚨 ROOT failed too many times. Halting execution.")
                            log_error("🚨 ROOT failed too many times. Halting execution.")
                            return
                    else:
                        log.error(f"⚠️ Step {self.next_step_id} failed too many times. Forcing replan.")
                        log_error(f"⚠️ Step {self.next_step_id} failed too many times. Forcing replan.")
                        self.next_step_id = StepType.ROOT
                continue

            self.ctx.mark_step_completed(self.next_step_id)

            log.info(f"✅ Step {self.next_step_id} completed successfully.")
            log.info(f"🔍 Running perception after execution")

            # 🔍 Perception after execution
            p_input = build_perception_input(self.query, self.memory, self.ctx, snapshot_type="step_result")
            self.p_out = await self.perception.run(p_input, session=self.session)


            self.ctx.attach_perception(self.next_step_id, self.p_out)
            log.info(f"📌 Perception output")
            logger_json_block(log,f"📌 Perception output ({self.next_step_id})", self.p_out)
            log_json_block(f"📌 Perception output ({self.next_step_id})", self.p_out)
            self.ctx._print_graph(depth=3)

            if self.p_out.get("original_goal_achieved") or self.p_out.get("route") == Route.SUMMARIZE:
                log.info(f"🔍 Original goal achieved or route is summarize, Now summarizing...")
                self.status = "success"
                self.final_output = await self._summarize()
                return

            if self.p_out.get("route") != Route.DECISION:
                log.error("🚩 Invalid route from perception. Exiting.")
                log_error("🚩 Invalid route from perception. Exiting.")
                return

            
            # 🔁 Decision again
            log.info(f"🔁 Running Decision again")
            
            d_input = build_decision_input(self.ctx, self.query, self.p_out, self.strategy)
            log.info(f"📌 Decision input")
            logger_json_block(log,f"📌 Decision input ({tracker.tries})", d_input)

            d_out = await self.decision.run(d_input, session=self.session)

            log.info(f"📌 Decision output")
            logger_json_block(log,f"📌 Decision output ({tracker.tries})", d_out)
            log_json_block(f"📌 Decision Output ({tracker.tries})", d_out)

            self.next_step_id = d_out["next_step_id"]
            self.code_variants = d_out["code_variants"]
            plan_graph = d_out["plan_graph"]
            self.update_plan_graph(self.ctx, plan_graph, self.next_step_id)


    async def _handle_failure(self):
        log_error(f"❌ Max steps reached. Halting at {self.next_step_id}")
        self.ctx._print_graph(depth=3)

        self.session.status = "failed"
        self.session.completed_at = datetime.utcnow().isoformat()

        save_final_plan(self.session_id, {
            "context": self.ctx.get_context_snapshot(),
            "session": self.session.to_json(),
            "status": "failed",
            "final_step_id": self.ctx.get_latest_node(),
            "reason": "Agent halted after max iterations or step failures.",
            "timestamp": datetime.utcnow().isoformat(),
            "original_query": self.ctx.original_query
        })

        return "⚠️ Agent halted after max iterations."

    def update_plan_graph(self, ctx, plan_graph, from_step_id):
        for node in plan_graph["nodes"]:
            step_id = node["id"]
            if step_id in ctx.graph.nodes:
                existing = ctx.graph.nodes[step_id]["data"]
                if existing.status != "pending":
                    continue
            ctx.add_step(step_id, description=node["description"], step_type=StepType.CODE, from_node=from_step_id)

    def _pick_next_step(self, ctx) -> str:
        for node_id in ctx.graph.nodes:
            node = ctx.graph.nodes[node_id]["data"]
            if node.status == "pending":
                return node.index
        return StepType.ROOT

    def _get_retry_step_id(self, step_id, failed_step_attempts):
        attempts = failed_step_attempts.get(step_id, 0)
        return f"{step_id}F{attempts}" if attempts > 0 else step_id


class StepExecutionTracker:
    def __init__(self, max_steps=12, max_retries=3):
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.attempts = {}
        self.tries = 0
        self.root_failures = 0

    def increment(self):
        self.tries += 1

    def record_failure(self, step_id):
        self.attempts[step_id] = self.attempts.get(step_id, 0) + 1

    def retry_step_id(self, step_id):
        attempts = self.attempts.get(step_id, 0)
        return f"{step_id}F{attempts}" if attempts > 0 else step_id

    def should_continue(self):
        return self.tries < self.max_steps

    def has_exceeded_retries(self, step_id):
        return self.attempts.get(step_id, 0) >= self.max_retries

    def register_root_failure(self):
        self.root_failures += 1
        return self.root_failures >= 2
