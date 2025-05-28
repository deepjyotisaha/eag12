class BrowserDecision:
    def decide(self, query, context=None):
        # Placeholder: simple keyword-based mapping
        plan = []
        q = query.lower()
        if "open" in q and ("http" in q or ".com" in q):
            # Extract URL (very basic)
            import re
            match = re.search(r'(https?://\S+|\b\w+\.com\b)', q)
            url = match.group(0) if match else None
            if url:
                plan.append({"action": "navigate", "url": url})
        if "search" in q:
            # Extract search term (very basic)
            import re
            match = re.search(r'search for ([\w\s]+)', q)
            term = match.group(1) if match else ""
            plan.append({"action": "search", "term": term})
        # Add more rules as needed
        if not plan:
            plan.append({"action": "unknown", "query": query})
        return plan 