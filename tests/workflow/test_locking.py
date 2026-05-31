from __future__ import annotations

import threading
from contextlib import AbstractContextManager

from aerosynthx.workflow.locking import RunLockRegistry


def test_same_key_is_mutually_exclusive() -> None:
    registry = RunLockRegistry()
    barrier = threading.Barrier(2)
    inside = 0
    max_inside = 0
    guard = threading.Lock()

    def worker() -> None:
        nonlocal inside, max_inside
        barrier.wait()
        with registry.acquire("run-a"):
            with guard:
                inside += 1
                max_inside = max(max_inside, inside)
            # Yield to encourage interleaving if exclusion were broken.
            for _ in range(1000):
                pass
            with guard:
                inside -= 1

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_inside == 1


def test_different_keys_run_concurrently() -> None:
    registry = RunLockRegistry()
    both_inside = threading.Barrier(2, timeout=5.0)

    def worker(key: str) -> None:
        with registry.acquire(key):
            # If distinct keys serialized, this barrier would deadlock and
            # time out, raising BrokenBarrierError.
            both_inside.wait()

    threads = [
        threading.Thread(target=worker, args=("run-a",)),
        threading.Thread(target=worker, args=("run-b",)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not both_inside.broken


def test_idle_entries_are_reclaimed() -> None:
    registry = RunLockRegistry()
    assert registry.active_keys == frozenset()
    with registry.acquire("run-a"):
        assert registry.active_keys == frozenset({"run-a"})
    assert registry.active_keys == frozenset()


def test_contention_is_observable() -> None:
    registry = RunLockRegistry()
    started = threading.Event()
    release = threading.Event()
    waiter_done = threading.Event()
    observed_contended: list[bool] = []

    def holder() -> None:
        with registry.acquire("run-a"):
            started.set()
            release.wait(timeout=5.0)

    def waiter() -> None:
        started.wait(timeout=5.0)
        # The key is already held, so _checkout must report contention.
        _entry, contended = registry._checkout("run-a")
        observed_contended.append(contended)
        registry._return("run-a")
        waiter_done.set()

    h = threading.Thread(target=holder)
    w = threading.Thread(target=waiter)
    h.start()
    w.start()
    waiter_done.wait(timeout=5.0)
    release.set()
    h.join()
    w.join()

    assert observed_contended == [True]


def test_lock_factory_is_injectable() -> None:
    created: list[int] = []

    def factory() -> AbstractContextManager[bool]:
        created.append(1)
        return threading.Lock()

    registry = RunLockRegistry(lock_factory=factory)
    with registry.acquire("run-a"):
        pass

    assert created == [1]
