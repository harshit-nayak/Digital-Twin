"""
backend/app/llm/round_robin.py

Thread-safe round-robin API key manager.
Tracks per-key cooldowns after rate-limit errors.
"""

import time
from threading import Lock


class AllKeysExhausted(Exception):
    pass


class RoundRobinKeyManager:
    """
    Rotates through a pool of API keys.
    When a key hits rate-limit, it's cooled down for `cooldown_seconds`
    and the next available key is returned.
    """

    def __init__(self, keys: list[str], provider: str):
        # Filter out empty / None keys
        self.keys     = [k for k in keys if k]
        self.provider = provider
        self.index    = 0
        self.cooldowns: dict[str, float] = {}
        self.lock     = Lock()

    def get_key(self) -> str:
        """
        Return the next available (non-cooled) key.
        Raises AllKeysExhausted if every key is currently on cooldown.
        """
        with self.lock:
            if not self.keys:
                raise AllKeysExhausted(f"No {self.provider} keys configured")

            now = time.time()
            for _ in range(len(self.keys)):
                key = self.keys[self.index % len(self.keys)]
                self.index += 1
                if self.cooldowns.get(key, 0) < now:
                    return key

            raise AllKeysExhausted(
                f"All {self.provider} keys are rate-limited. "
                f"Retry after: {min(self.cooldowns.values()) - now:.0f}s"
            )

    def mark_rate_limited(self, key: str, cooldown_seconds: int = 60):
        """Put a key on cooldown after a 429 / rate-limit response."""
        with self.lock:
            self.cooldowns[key] = time.time() + cooldown_seconds
            print(
                f"[RoundRobin] {self.provider} key ...{key[-6:]} "
                f"cooling down for {cooldown_seconds}s"
            )

    def available_count(self) -> int:
        """How many keys are currently off cooldown."""
        now = time.time()
        return sum(1 for k in self.keys if self.cooldowns.get(k, 0) < now)

    def status(self) -> dict:
        """Debug: return status of all keys."""
        now = time.time()
        return {
            k[-6:]: "ok" if self.cooldowns.get(k, 0) < now
                    else f"cooling ({self.cooldowns[k] - now:.0f}s)"
            for k in self.keys
        }
