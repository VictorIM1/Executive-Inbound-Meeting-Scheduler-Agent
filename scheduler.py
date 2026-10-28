"""Autonomous background polling and inbound processing engine."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List
from uuid import uuid4

from apscheduler.schedulers.background import BackgroundScheduler

from agent import run_agent, state_to_tracker_record
from tracker import append_or_update_record, init_tracker, load_all_records


class MockInbox:
    """In-memory inbound queue used for local/demo execution."""

    def __init__(self) -> None:
        self._queue: List[Dict[str, str]] = [
            {
                "email_id": "demo-001",
                "received_timestamp": "2026-10-28T08:00:00Z",
                "raw_email_body": (
                    "Hi team, this is Sofia Patel from Northlight Capital. "
                    "Could we schedule a 30-minute executive intro meeting tomorrow?"
                ),
            },
            {
                "email_id": "demo-002",
                "received_timestamp": "2026-10-28T08:15:00Z",
                "raw_email_body": (
                    "Hello, I'm Marcus Lee at VentureBridge Partners. "
                    "Please pick any slot through my Calendly: https://calendly.com/marcus-vb/exec-intro"
                ),
            },
            {
                "email_id": "demo-003",
                "received_timestamp": "2026-10-28T08:25:00Z",
                "raw_email_body": "Weekly market newsletter: top 10 headlines and product updates.",
            },
        ]

    def pop_next(self) -> Dict[str, str] | None:
        if self._queue:
            return self._queue.pop(0)
        return None

    def add_demo_message(self) -> Dict[str, str]:
        email_id = f"demo-{uuid4().hex[:8]}"
        payload = {
            "email_id": email_id,
            "received_timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_email_body": (
                "Hi, this is Elena Rossi from Atlas Dynamics. "
                "Would Thursday work for an executive partnership discussion?"
            ),
        }
        self._queue.append(payload)
        return payload


_scheduler: BackgroundScheduler | None = None
_lock = Lock()
_inbox = MockInbox()


def _process_one_inbound() -> Dict[str, str] | None:
    message = _inbox.pop_next()
    if not message:
        return None

    state = run_agent(
        email_id=message["email_id"],
        received_timestamp=message["received_timestamp"],
        raw_email_body=message["raw_email_body"],
    )
    record = state_to_tracker_record(state)
    append_or_update_record(record)
    return record


def run_poll_cycle(max_items: int = 3) -> List[Dict[str, str]]:
    """Process up to max_items from mock inbox in one autonomous cycle."""

    init_tracker()
    processed: List[Dict[str, str]] = []
    with _lock:
        for _ in range(max_items):
            record = _process_one_inbound()
            if not record:
                break
            processed.append(record)
    return processed


def start_background_scheduler(interval_seconds: int = 30) -> BackgroundScheduler:
    """Start background scheduler for autonomous inbound polling."""

    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    init_tracker()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=run_poll_cycle,
        trigger="interval",
        seconds=max(5, interval_seconds),
        id="inbound_poller",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def trigger_immediate_run() -> List[Dict[str, str]]:
    """Force an immediate processing cycle and ensure there is content to process."""

    current = load_all_records()
    known_ids = set(current["email_id"].astype(str).tolist()) if not current.empty else set()

    # Ensure every manual trigger demonstrates ingestion by appending a fresh sample.
    sample = _inbox.add_demo_message()
    if sample["email_id"] in known_ids:
        _inbox.add_demo_message()

    return run_poll_cycle(max_items=1)


def scheduler_status() -> str:
    """Return friendly scheduler status for UI display."""

    if _scheduler and _scheduler.running:
        return "Active"
    return "Inactive"
