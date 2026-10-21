"""Minimal job model: chunked work with progress and cooperative cancel."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class JobState(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DONE = "DONE"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


@dataclass
class Job:
    name: str
    steps: int = 1
    state: JobState = JobState.QUEUED
    done: int = 0
    message: str = ""
    error: str = ""
    cancel_requested: bool = False
    started: float = field(default=0.0)
    finished: float = field(default=0.0)

    @property
    def progress(self) -> float:
        return self.done / self.steps if self.steps else 1.0

    def start(self):
        self.state = JobState.RUNNING
        self.started = time.time()

    def advance(self, message: str = "", n: int = 1):
        self.done += n
        if message:
            self.message = message

    def cancel(self):
        self.cancel_requested = True

    def finish(self):
        self.state = JobState.CANCELLED if self.cancel_requested and self.done < self.steps else JobState.DONE
        self.finished = time.time()

    def fail(self, error: str):
        self.state = JobState.FAILED
        self.error = error
        self.finished = time.time()


def run(job: Job, work):
    """Run `work` (a generator yielding progress messages) to completion or cancel."""
    job.start()
    try:
        for msg in work:
            job.advance(str(msg) if msg else "")
            if job.cancel_requested:
                break
    except Exception as exc:  # noqa: BLE001 - surface to UI
        job.fail(repr(exc))
        return job
    job.finish()
    return job
