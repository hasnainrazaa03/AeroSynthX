from __future__ import annotations

import pytest

from aerosynthx.workflow.cancellation import (
    CancellationToken,
    Deadline,
    RunControl,
)
from aerosynthx.workflow.errors import RunCancelledError, RunTimeoutError


class _FakeClock:
    """A deterministic monotonic clock driven by a value queue."""

    def __init__(self, *values: float) -> None:
        self._values = list(values)
        self._last = values[-1] if values else 0.0

    def __call__(self) -> float:
        if self._values:
            self._last = self._values.pop(0)
        return self._last


# --- CancellationToken ------------------------------------------------


def test_token_starts_uncancelled() -> None:
    token = CancellationToken()
    assert token.cancelled is False


def test_token_cancel_is_idempotent() -> None:
    token = CancellationToken()
    token.cancel()
    token.cancel()
    assert token.cancelled is True


# --- Deadline ---------------------------------------------------------


def test_deadline_unbounded_never_expires() -> None:
    deadline = Deadline.start(None, clock=_FakeClock(100.0))
    assert deadline.expired is False
    assert deadline.remaining() is None


def test_deadline_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        Deadline.start(0, clock=_FakeClock(0.0))


def test_deadline_not_expired_within_budget() -> None:
    # start() reads clock once (0.0) -> deadline = 5.0; expired() reads 1.0.
    deadline = Deadline.start(5.0, clock=_FakeClock(0.0, 1.0))
    assert deadline.expired is False


def test_deadline_expired_past_budget() -> None:
    deadline = Deadline.start(5.0, clock=_FakeClock(0.0, 9.0))
    assert deadline.expired is True


def test_deadline_remaining_counts_down() -> None:
    deadline = Deadline.start(5.0, clock=_FakeClock(0.0, 2.0))
    assert deadline.remaining() == pytest.approx(3.0)


def test_deadline_uses_real_clock_by_default() -> None:
    deadline = Deadline.start(60.0)
    assert deadline.expired is False
    remaining = deadline.remaining()
    assert remaining is not None and remaining > 0.0


# --- RunControl -------------------------------------------------------


def test_control_check_passes_when_unbounded_and_uncancelled() -> None:
    control = RunControl.create(timeout=None, cancel_token=None)
    control.check("parse")  # must not raise


def test_control_check_passes_with_live_token_and_budget() -> None:
    token = CancellationToken()
    control = RunControl.create(timeout=5.0, cancel_token=token, clock=_FakeClock(0.0, 1.0))
    control.check("parse")  # token live, budget remaining -> no raise


def test_control_check_raises_on_cancel() -> None:
    token = CancellationToken()
    token.cancel()
    control = RunControl.create(timeout=None, cancel_token=token)
    with pytest.raises(RunCancelledError) as excinfo:
        control.check("compute")
    assert excinfo.value.stage == "compute"
    assert excinfo.value.code == "workflow.run.cancelled"


def test_control_check_raises_on_timeout() -> None:
    control = RunControl.create(timeout=1.0, cancel_token=None, clock=_FakeClock(0.0, 5.0))
    with pytest.raises(RunTimeoutError) as excinfo:
        control.check("case")
    assert excinfo.value.stage == "case"
    assert excinfo.value.code == "workflow.run.timeout"


def test_control_cancel_wins_over_timeout() -> None:
    token = CancellationToken()
    token.cancel()
    control = RunControl.create(timeout=1.0, cancel_token=token, clock=_FakeClock(0.0, 5.0))
    with pytest.raises(RunCancelledError):
        control.check("parse")


def test_solver_timeout_unbounded_returns_default() -> None:
    control = RunControl.create(timeout=None, cancel_token=None)
    assert control.solver_timeout(600.0) == 600.0


def test_solver_timeout_capped_by_remaining_budget() -> None:
    control = RunControl.create(timeout=10.0, cancel_token=None, clock=_FakeClock(0.0, 2.0))
    assert control.solver_timeout(600.0) == pytest.approx(8.0)


def test_solver_timeout_floors_at_zero() -> None:
    control = RunControl.create(timeout=1.0, cancel_token=None, clock=_FakeClock(0.0, 5.0))
    assert control.solver_timeout(600.0) == 0.0
