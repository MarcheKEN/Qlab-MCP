from __future__ import annotations

import threading
import unittest

from qlab_mcp.runtime.read_cache import ReadCache


class ReadCacheTests(unittest.TestCase):
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
