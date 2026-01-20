from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Protocol


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True)
class StepInfo:
    id: str
    label: str
    weight: int


@dataclass(frozen=True)
class StepUpdate:
    step_id: str
    status: StepStatus
    detail: str
    local_progress: int = 0


class ReporterProtocol(Protocol):
    def on_setup_steps(self, steps: List[StepInfo]) -> None:
        """Receive the full step list before execution."""

    def on_update(self, update: StepUpdate) -> None:
        """Receive step status updates."""


@dataclass(frozen=True)
class StepContext:
    step_id: str
    reporter: ReporterProtocol | None
    start_detail: str
    success_detail: str | Callable[[], str]

    def __enter__(self):
        if self.reporter:
            self.reporter.on_update(
                StepUpdate(self.step_id, StepStatus.RUNNING, self.start_detail, 0)
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self.reporter:
            return False
        if exc is None:
            detail = self.success_detail if isinstance(self.success_detail, str) else self.success_detail()
            self.reporter.on_update(
                StepUpdate(self.step_id, StepStatus.SUCCESS, detail, 100)
            )
            return False
        self.reporter.on_update(
            StepUpdate(self.step_id, StepStatus.FAILED, str(exc), 0)
        )
        return False


def step_context(
    step_id: str,
    reporter: ReporterProtocol | None,
    start_detail: str,
    success_detail: str | Callable[[], str],
) -> StepContext:
    return StepContext(step_id, reporter, start_detail, success_detail)
