"""Token Budget Manager — initial simple implementation."""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    """Simple token budget tracker."""
    total_budget: int = 100000
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.total_budget - self.used)

    def consume(self, tokens: int) -> bool:
        """Consume tokens. Returns False if over budget."""
        if self.used + tokens > self.total_budget:
            return False
        self.used += tokens
        return True

    def reset(self):
        self.used = 0
