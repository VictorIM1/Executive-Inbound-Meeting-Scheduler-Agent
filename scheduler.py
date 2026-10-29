"""Background scheduler handling periodic inbox polling and agent routing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
<<<<<<< Updated upstream
from threading import Lock
from typing import Dict, List, Tuple
from uuid import uuid4
=======
from typing import Any, Dict, List
import uuid
>>>>>>> Stashed changes

from apscheduler.schedulers.background import BackgroundScheduler

from agent import run_agent, state_to_tracker_record
<<<<<<< Updated upstream
from google_service import dispatch_email_reply, fetch_free_calendar_slots, fetch_real_inbound_emails, google_auth_status
from tracker import append_or_update_record, init_tracker, load_all_records


class MockInbox:
    """In-memory inbound queue used for local/demo execution."""

    def __init__(self) -> None:
        self._queue: List[Dict[str, str]] = [
            {
                "id": "demo-001",
                "threadId": "",
                "sender": "Sofia Patel <sofia@northlight.example>",
                "recipient": "sofia@northlight.example",
                "subject": "Executive intro request",
                "date": "2026-10-28T08:00:00Z",
                "raw_body": "Hi team, this is Sofia Patel from Northlight Capital. Could we schedule a 30-minute executive intro meeting tomorrow?",
                "snippet": "Could we schedule a 30-minute executive intro meeting tomorrow?",
            },
            {
                "id": "demo-002",
                "threadId": "",
                "sender": "Marcus Lee <marcus@venturebridge.example>",
                "recipient": "marcus@venturebridge.example",
                "subject": "Calendly for partner intro",
                "date": "2026-10-28T08:15:00Z",
                "raw_body": "Hello, I'm Marcus Lee at VentureBridge Partners. Please pick any slot through my Calendly: https://calendly.com/marcus-vb/exec-intro",
                "snippet": "Please pick any slot through my Calendly",
            },
            {
                "id": "demo-003",
                "threadId": "",
                "sender": "Market Digest <news@digest.example>",
                "recipient": "news@digest.example",
                "subject": "Weekly market digest",
                "date": "2026-10-28T08:25:00Z",
                "raw_body": "Weekly market newsletter: top 10 headlines and product updates.",
                "snippet": "Weekly market newsletter",
            },
        ]

    def pop_next(self) -> Dict[str, str] | None:
        if self._queue:
            return self._queue.pop(0)
        return None

    def add_demo_message(self) -> Dict[str, str]:
        email_id = f"demo-{uuid4().hex[:8]}"
        payload = {
            "id": email_id,
            "threadId": "",
            "sender": "Elena Rossi <elena@atlas.example>",
            "recipient": "elena@atlas.example",
            "subject": "Partnership discussion",
            "date": datetime.now(timezone.utc).isoformat(),
            "raw_body": "Hi, this is Elena Rossi from Atlas Dynamics. Would Thursday work for an executive partnership discussion?",
            "snippet": "Would Thursday work for an executive partnership discussion?",
        }
        self._queue.append(payload)
        return payload


_scheduler: BackgroundScheduler | None = None
_lock = Lock()
_inbox = MockInbox()


def _resolve_data_source(requested: str) -> Tuple[str, str]:
    mode = requested.upper()
    if mode != "LIVE":
        return "MOCK", "mock mode selected"

    status = google_auth_status()
    if status.get("token_valid"):
        return "LIVE", "live token valid"
    return "MOCK", f"live unavailable ({status.get('detail', 'unknown issue')}); using MOCK"


def _live_messages(max_items: int) -> Tuple[List[Dict[str, str]], str]:
    messages, detail = fetch_real_inbound_emails(max_results=max_items)
    return messages, detail


def _mock_messages(max_items: int) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    for _ in range(max_items):
        msg = _inbox.pop_next()
        if not msg:
            break
        messages.append(msg)
    return messages


def _calendar_slots(data_source: str) -> List[str]:
    if data_source == "LIVE":
        slots, detail = fetch_free_calendar_slots(days_ahead=3)
        if slots:
            return slots
        if "ok" not in detail:
            return []
    return ["Tomorrow at 14:00 EET", "Thursday at 10:30 EET", "Friday at 16:00 EET"]


def _process_message(message: Dict[str, str], data_source: str, calendar_slots: List[str]) -> Dict[str, str]:
    state = run_agent(
        email_id=message.get("id", ""),
        thread_id=message.get("threadId", ""),
        sender=message.get("sender", "Unknown Sender"),
        recipient=message.get("recipient", ""),
        subject=message.get("subject", "No Subject"),
        received_timestamp=message.get("date", datetime.now(timezone.utc).isoformat()),
        raw_email_body=message.get("raw_body") or message.get("snippet", ""),
        available_calendar_slots=calendar_slots,
    )
    record = state_to_tracker_record(state)
    record["data_source"] = data_source
    append_or_update_record(record)
    return record


def run_poll_cycle(max_items: int = 3, data_source: str = "MOCK") -> List[Dict[str, str]]:
    """Process up to max_items from live inbox or mock queue in one cycle."""

    init_tracker()
    requested_mode = (data_source or "MOCK").upper()
    effective_mode, _ = _resolve_data_source(requested_mode)

    known_ids = set()
    current = load_all_records()
    if not current.empty:
        known_ids = set(current["email_id"].astype(str).tolist())

    with _lock:
        if effective_mode == "LIVE":
            incoming, _ = _live_messages(max_items=max_items)
        else:
            incoming = _mock_messages(max_items=max_items)

        slots = _calendar_slots(effective_mode)
        processed: List[Dict[str, str]] = []
        for message in incoming:
            if message.get("id", "") in known_ids:
                continue
            record = _process_message(message, effective_mode, slots)
            processed.append(record)
            known_ids.add(message.get("id", ""))

    return processed


def start_background_scheduler(interval_seconds: int = 30, data_source: str = "MOCK") -> BackgroundScheduler:
    """Start background scheduler for autonomous inbound polling."""

    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)

    init_tracker()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=run_poll_cycle,
        kwargs={"max_items": 3, "data_source": data_source},
=======
from tracker import append_or_update_record, load_all_records

try:
    from google_services import fetch_real_emails, get_gmail_service
except ImportError:
    get_gmail_service = None
    fetch_real_emails = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_SCHEDULER = BackgroundScheduler()


def _generate_mock_inbound(index: int) -> Dict[str, Any]:
    """Fallback generator for mock data if live mode is inactive."""
    now = datetime.now(timezone.utc)
    return {
        "email_id": f"demo-{uuid.uuid4().hex[:8]}",
        "received_timestamp": now.isoformat(),
        "sender": "Elena Rossi",
        "raw_email_body": f"Hi team, this is Elena from Atlas Dynamics. Could we schedule a brief intro call on Thursday?",
    }


def run_poll_cycle(max_items: int = 3, live_mode: bool = True) -> List[Dict[str, str]]:
    """Fetch recent inbound emails (live or mock) and route them through the agent graph."""
    processed_records = []
    
    records_df = load_all_records()
    known_ids = set(records_df["email_id"].astype(str).tolist()) if not records_df.empty else set()

    inbound_batch = []
    if live_mode and get_gmail_service and fetch_real_emails:
        try:
            svc = get_gmail_service()
            real_emails = fetch_real_emails(svc, max_results=max_items)
            for e in real_emails:
                inbound_batch.append({
                    "email_id": e["email_id"],
                    "received_timestamp": e["date"],
                    "sender": e["sender"],
                    "raw_email_body": f"From: {e['sender']}\nSubject: {e['subject']}\n\n{e['body']}"
                })
        except Exception as e:
            logger.error(f"[Scheduler] Eroare preluare Gmail API: {e}. Fallback la mock.")
            for i in range(max_items):
                inbound_batch.append(_generate_mock_inbound(i))
    else:
        for i in range(max_items):
            inbound_batch.append(_generate_mock_inbound(i))

    for email_data in inbound_batch:
        if email_data["email_id"] in known_ids:
            continue

        try:
            final_state = run_agent(
                email_id=email_data["email_id"],
                received_timestamp=email_data["received_timestamp"],
                raw_email_body=email_data["raw_email_body"],
            )
            record = state_to_tracker_record(final_state)
            append_or_update_record(record)
            processed_records.append(record)
            known_ids.add(email_data["email_id"])
        except Exception as e:
            logger.error(f"Error processing email {email_data['email_id']}: {e}")

    if processed_records:
        logger.info(f"[Scheduler] Processed {len(processed_records)} new inbound items.")
    return processed_records


def start_background_scheduler(interval_seconds: int = 60) -> None:
    """Start the APScheduler background job. Defaults to live_mode=True."""
    if _SCHEDULER.running:
        return

    _SCHEDULER.add_job(
        func=lambda: run_poll_cycle(max_items=3, live_mode=True),
>>>>>>> Stashed changes
        trigger="interval",
        seconds=max(5, interval_seconds),
        id="inbound_poller",
        replace_existing=True,
    )
    _SCHEDULER.start()
    logger.info(f"Background scheduler started. Polling every {interval_seconds} seconds.")

<<<<<<< Updated upstream
def trigger_immediate_run(data_source: str = "MOCK") -> Tuple[List[Dict[str, str]], str]:
    """Force an immediate processing cycle and return the effective mode message."""

    requested_mode = (data_source or "MOCK").upper()
    effective_mode, status_message = _resolve_data_source(requested_mode)

    if effective_mode == "MOCK":
        _inbox.add_demo_message()

    processed = run_poll_cycle(max_items=5 if effective_mode == "LIVE" else 1, data_source=effective_mode)
    return processed, status_message


def dispatch_approved_reply_for_record(email_id: str, final_draft: str, data_source: str = "MOCK") -> Tuple[bool, str]:
    """Dispatch approved response through Gmail in LIVE mode; no-op in MOCK mode."""

    if (data_source or "MOCK").upper() != "LIVE":
        return True, "mock mode: dispatch skipped"

    effective_mode, status_message = _resolve_data_source("LIVE")
    if effective_mode != "LIVE":
        return False, status_message

    records = load_all_records()
    if records.empty:
        return False, "tracker is empty"

    match = records[records["email_id"].astype(str) == str(email_id)]
    if match.empty:
        return False, f"email_id {email_id} not found"

    row = match.iloc[0]
    recipient = str(row.get("recipient", "")).strip()
    thread_id = str(row.get("thread_id", "")).strip()
    subject = str(row.get("subject", "No Subject")).strip() or "No Subject"

    if not recipient or not thread_id:
        return False, "missing recipient/thread for live dispatch"

    return dispatch_email_reply(
        thread_id=thread_id,
        recipient=recipient,
        subject=subject,
        body_text=final_draft,
        message_id=str(row.get("email_id", "")).strip() or None,
    )
=======

def trigger_immediate_run(live_mode: bool = True) -> List[Dict[str, str]]:
    """Manually invoke the polling cycle."""
    return run_poll_cycle(max_items=3, live_mode=live_mode)
>>>>>>> Stashed changes


def scheduler_status() -> str:
    return "Active" if _SCHEDULER.running else "Inactive"