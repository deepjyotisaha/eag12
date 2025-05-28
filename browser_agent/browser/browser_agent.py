from .browser_decision import BrowserDecision
from .browser_action import BrowserAction

class BrowserAgent:
    def __init__(self):
        self.decision = BrowserDecision()
        self.action = BrowserAction()

    async def run(self, query, context=None):
        # Decide what browser action(s) to take
        action_plan = self.decision.decide(query, context)
        # Execute the action(s)
        result = await self.action.execute(action_plan, context)
        return result 