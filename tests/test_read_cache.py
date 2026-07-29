from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from qlab_mcp.runtime.read_cache import ReadCache, _CacheEntry


class ReadCacheTests(unittest.TestCase):
    def test_expiry_time_is_sampled_while_cache_lock_is_held(self) -> None:
        cache = ReadCache()

        def monotonic() -> float:
            self.assertTrue(cache._lock.locked())
            return 1.0

        with patch("qlab_mcp.runtime.read_cache.time.monotonic", side_effect=monotonic):
            self.assertEqual(cache.get_or_set("key", 10, lambda: "value"), "value")

    def test_slow_factory_ttl_starts_after_factory_completes(self) -> None:
        cache = ReadCache()
        factory_calls = 0

        def factory() -> str:
            nonlocal factory_calls
            factory_calls += 1
            return "value"

        with patch("qlab_mcp.runtime.read_cache.time.monotonic", side_effect=[10.0, 20.0, 25.0]):
            self.assertEqual(cache.get_or_set("key", 10, factory), "value")
            self.assertEqual(cache.get_or_set("key", 10, factory), "value")

        self.assertEqual(factory_calls, 1)

    def test_cache_access_prunes_expired_untouched_keys(self) -> None:
        cache = ReadCache()
        cache._entries["expired"] = _CacheEntry(expires_at=1.0, value="old")

        with patch("qlab_mcp.runtime.read_cache.time.monotonic", return_value=2.0):
            self.assertEqual(cache.get_or_set("fresh", 10, lambda: "new"), "new")

        self.assertNotIn("expired", cache._entries)

    def test_waiter_timeout_does_not_start_second_factory(self) -> None:
        cache = ReadCache()
        started = threading.Event()
        release = threading.Event()
        owner_result: list[str] = []
        factory_calls = 0

        def factory() -> str:
            nonlocal factory_calls
            factory_calls += 1
            started.set()
            self.assertTrue(release.wait(timeout=1))
            return "owner"

        owner = threading.Thread(target=lambda: owner_result.append(cache.get_or_set("key", 10, factory)))
        owner.start()
        self.assertTrue(started.wait(timeout=1))

        try:
            with self.assertRaises(TimeoutError):
                cache.get_or_set("key", 10, lambda: "waiter", wait_timeout=0.01)
        finally:
            release.set()
            owner.join(timeout=1)
        self.assertFalse(owner.is_alive())
        self.assertEqual(owner_result, ["owner"])
        self.assertEqual(factory_calls, 1)

    def test_clear_does_not_allow_inflight_value_to_repopulate_cache(self) -> None:
        cache = ReadCache()
        started = threading.Event()
        release = threading.Event()
        result: list[str] = []

        def stale_factory() -> str:
            started.set()
            self.assertTrue(release.wait(timeout=1))
            return "stale"

        owner = threading.Thread(
            target=lambda: result.append(cache.get_or_set("key", 10, stale_factory))
        )
        owner.start()
        self.assertTrue(started.wait(timeout=1))

        cache.clear()
        release.set()
        owner.join(timeout=1)

        self.assertFalse(owner.is_alive())
        self.assertEqual(result, ["stale"])
        self.assertEqual(cache.get_or_set("key", 10, lambda: "fresh"), "fresh")

    def test_old_owner_cannot_remove_new_inflight_entry_after_clear(self) -> None:
        cache = ReadCache()
        old_started = threading.Event()
        old_release = threading.Event()
        new_started = threading.Event()
        new_release = threading.Event()
        results: list[str] = []

        def old_factory() -> str:
            old_started.set()
            self.assertTrue(old_release.wait(timeout=1))
            return "old"

        def new_factory() -> str:
            new_started.set()
            self.assertTrue(new_release.wait(timeout=1))
            return "new"

        old_owner = threading.Thread(
            target=lambda: results.append(cache.get_or_set("key", 10, old_factory))
        )
        old_owner.start()
        self.assertTrue(old_started.wait(timeout=1))

        cache.clear()
        new_owner = threading.Thread(
            target=lambda: results.append(cache.get_or_set("key", 10, new_factory))
        )
        new_owner.start()
        self.assertTrue(new_started.wait(timeout=1))
        with cache._lock:
            new_inflight = cache._inflight["key"]

        old_release.set()
        old_owner.join(timeout=1)
        self.assertFalse(old_owner.is_alive())

        # The new owner must still be in flight after the old owner finishes.
        with cache._lock:
            self.assertIs(cache._inflight["key"], new_inflight)

        new_release.set()
        new_owner.join(timeout=1)
        self.assertFalse(new_owner.is_alive())
        self.assertCountEqual(results, ["old", "new"])


if __name__ == "__main__":
    unittest.main()
