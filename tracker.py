"""Excel-backed persistence helpers for inbound meeting workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

TRACKER_PATH = Path(__file__).resolve().parent / "meetings_tracker.xlsx"
COLUMNS = [
    "email_id",
    "thread_id",
    "received_date",
    "subject",
    "recipient",
    "sender",
    "company",
    "topic",
    "status",
    "data_source",
    "has_booking_link",
    "selected_or_offered_slots",
    "draft_preview",
    "executive_notes",
    "raw_email_body",
    "received_timestamp",
    "booking_url",
    "validated_slots",
    "validation_passed",
    "validation_notes",
]

_MEMORY_TRACKER_DF = pd.DataFrame(columns=COLUMNS)


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def _safe_read_excel() -> pd.DataFrame:
    global _MEMORY_TRACKER_DF
    if TRACKER_PATH.exists():
        try:
            df = pd.read_excel(TRACKER_PATH)
            for column in COLUMNS:
                if column not in df.columns:
                    df[column] = ""
            return df[COLUMNS]
        except Exception:
            return _MEMORY_TRACKER_DF.copy()
    return _MEMORY_TRACKER_DF.copy()


def _safe_write(df: pd.DataFrame) -> None:
    global _MEMORY_TRACKER_DF
    normalized = df.copy()
    for column in COLUMNS:
        if column not in normalized.columns:
            normalized[column] = ""
    normalized = normalized[COLUMNS]
    _MEMORY_TRACKER_DF = normalized.copy()
    try:
        normalized.to_excel(TRACKER_PATH, index=False)
    except Exception:
        # Keep in-memory fallback if local file writing fails.
        pass


def init_tracker() -> pd.DataFrame:
    """Initialize tracker with historical rows when no persistent data exists."""

    existing = _safe_read_excel()
    if not existing.empty:
        return existing

    seed_rows = [
        {
            "email_id": "hist-001",
            "thread_id": "",
            "received_date": "2026-10-21",
            "subject": "Portfolio strategy sync",
            "recipient": "nadia@example.com",
            "sender": "Nadia Farouk",
            "company": "Helios Ventures",
            "topic": "Portfolio strategy sync",
            "status": "Approved & Sent",
            "data_source": "MOCK",
            "has_booking_link": False,
            "selected_or_offered_slots": "Wednesday at 10:30 EET",
            "draft_preview": "Thanks Nadia — Wednesday at 10:30 EET works for the executive team.",
            "executive_notes": "High-priority partner; keep monthly cadence.",
            "raw_email_body": "",
            "received_timestamp": "2026-10-21T09:10:00Z",
            "booking_url": "",
            "validated_slots": "Wednesday at 10:30 EET",
            "validation_passed": True,
            "validation_notes": "Historical approved record.",
        },
        {
            "email_id": "hist-002",
            "thread_id": "",
            "received_date": "2026-10-22",
            "subject": "Weekly newsletter",
            "recipient": "",
            "sender": "Market Digest",
            "company": "",
            "topic": "Weekly newsletter",
            "status": "Rejected / Archived",
            "data_source": "MOCK",
            "has_booking_link": False,
            "selected_or_offered_slots": "",
            "draft_preview": "",
            "executive_notes": "Informational only.",
            "raw_email_body": "",
            "received_timestamp": "2026-10-22T07:30:00Z",
            "booking_url": "",
            "validated_slots": "",
            "validation_passed": False,
            "validation_notes": "Non-meeting content.",
        },
    ]
    df = pd.DataFrame(seed_rows, columns=COLUMNS)
    _safe_write(df)
    return df


def append_or_update_record(record_dict: Dict[str, Any]) -> pd.DataFrame:
    """Upsert a record in the tracker keyed by email_id."""

    if "email_id" not in record_dict or not str(record_dict["email_id"]).strip():
        raise ValueError("record_dict must include non-empty 'email_id'.")

    current = _safe_read_excel()
    if current.empty:
        current = _empty_df()
    current = current.astype(object)

    for column in COLUMNS:
        if column not in record_dict:
            record_dict[column] = ""

    email_id = str(record_dict["email_id"])
    match_index = current.index[current["email_id"].astype(str) == email_id].tolist()
    new_row = pd.DataFrame([record_dict], columns=COLUMNS).astype(object)

    if match_index:
        current.loc[match_index[0], COLUMNS] = new_row.iloc[0]
    else:
        current = pd.concat([current, new_row], ignore_index=True)

    _safe_write(current)
    return current


def get_pending_reviews() -> pd.DataFrame:
    """Return records queued for human review."""

    current = _safe_read_excel()
    if current.empty:
        return _empty_df()
    return current[current["status"].astype(str) == "Pending Review"].copy()


def update_status_and_notes(
    email_id: str,
    new_status: str,
    notes: Optional[str],
    final_draft: Optional[str],
) -> pd.DataFrame:
    """Update status, executive notes, and final draft for one inbound item."""

    current = _safe_read_excel()
    if current.empty:
        raise ValueError("Tracker is empty; cannot update status.")
    current = current.astype(object)

    target = current["email_id"].astype(str) == str(email_id)
    if not target.any():
        raise ValueError(f"No record found for email_id={email_id!r}")

    current.loc[target, "status"] = new_status
    current.loc[target, "executive_notes"] = notes or ""
    current.loc[target, "draft_preview"] = final_draft or ""

    _safe_write(current)
    return current


def load_all_records() -> pd.DataFrame:
    """Return all records from storage, ensuring initialization first."""

    init_tracker()
    return _safe_read_excel()


def to_record_dicts(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert a dataframe into serializable records for UI usage."""

    if df.empty:
        return []
    return df.fillna("").to_dict(orient="records")
