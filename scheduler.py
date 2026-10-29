"""Background scheduler handling periodic inbox polling and agent routing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid

from apscheduler.schedulers.background import BackgroundScheduler

from agent import run_agent, state_to_tracker_record
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
        trigger="interval",
        seconds=max(5, interval_seconds),
        id="inbound_poller",
        replace_existing=True,
    )
    _SCHEDULER.start()
    logger.info(f"Background scheduler started. Polling every {interval_seconds} seconds.")


def trigger_immediate_run(live_mode: bool = True) -> List[Dict[str, str]]:
    """Manually invoke the polling cycle."""
    return run_poll_cycle(max_items=3, live_mode=live_mode)


def scheduler_status() -> str:
    return "Active" if _SCHEDULER.running else "Inactive"