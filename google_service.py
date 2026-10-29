"""Google Gmail/Calendar integration with defensive OAuth handling."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_PATH = Path(__file__).resolve().parent / "token.json"
CREDENTIALS_PATH = Path(__file__).resolve().parent / "credentials.json"
LOGGER = logging.getLogger(__name__)


def _load_credentials() -> Tuple[Optional[Credentials], str]:
    """Load and refresh OAuth credentials without interactive/headful login."""

    if not TOKEN_PATH.exists():
        return None, "token.json not found"

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    except Exception as exc:
        return None, f"token.json invalid: {exc}"

    if creds.valid:
        return creds, "token.json valid"

    if not creds.expired:
        return None, "token.json present but credentials are invalid"

    if not creds.refresh_token:
        return None, "token.json missing refresh token"

    try:
        if CREDENTIALS_PATH.exists() and not creds.client_id:
            creds_with_client = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            if creds_with_client:
                creds = creds_with_client
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        return creds, "token refreshed"
    except Exception as exc:
        LOGGER.warning("OAuth refresh failed; staying in mock-safe mode: %s", exc)
        return None, f"token refresh failed: {exc}"


def google_auth_status() -> Dict[str, Any]:
    """Return current OAuth readiness status for UI diagnostics."""

    token_exists = TOKEN_PATH.exists()
    creds, detail = _load_credentials()
    return {
        "token_detected": token_exists,
        "token_valid": creds is not None,
        "detail": detail,
    }


def _build_services() -> Tuple[Optional[Any], Optional[Any], str]:
    creds, detail = _load_credentials()
    if not creds:
        return None, None, detail

    try:
        gmail_service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        calendar_service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return gmail_service, calendar_service, "ok"
    except Exception as exc:
        return None, None, f"google service initialization failed: {exc}"


def _decode_part_body(data: str) -> str:
    if not data:
        return ""
    try:
        decoded = base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")
        return decoded.strip()
    except Exception:
        return ""


def _extract_message_text(payload: Dict[str, Any]) -> str:
    body_data = payload.get("body", {}).get("data")
    text = _decode_part_body(body_data)
    if text:
        return text

    for part in payload.get("parts", []) or []:
        mime_type = part.get("mimeType", "")
        part_body = _decode_part_body(part.get("body", {}).get("data", ""))
        if mime_type in {"text/plain", "text/html"} and part_body:
            return part_body
    return ""


def _header_map(payload: Dict[str, Any]) -> Dict[str, str]:
    headers = payload.get("headers", []) or []
    return {h.get("name", "").lower(): h.get("value", "") for h in headers if h.get("name")}


def fetch_real_inbound_emails(max_results: int = 5) -> Tuple[List[Dict[str, str]], str]:
    """Fetch unread inbox emails from Gmail and normalize message metadata."""

    gmail_service, _, detail = _build_services()
    if not gmail_service:
        return [], detail

    try:
        response = (
            gmail_service.users()
            .messages()
            .list(userId="me", q="is:unread in:inbox", maxResults=max(1, max_results))
            .execute()
        )
        messages = response.get("messages", [])
        normalized: List[Dict[str, str]] = []
        for msg in messages:
            msg_id = msg.get("id", "")
            if not msg_id:
                continue
            full_message = (
                gmail_service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
            payload = full_message.get("payload", {})
            headers = _header_map(payload)
            sender = headers.get("from", "Unknown Sender")
            subject = headers.get("subject", "No Subject")
            date = headers.get("date", "")
            raw_body = _extract_message_text(payload) or full_message.get("snippet", "")
            normalized.append(
                {
                    "id": msg_id,
                    "threadId": full_message.get("threadId", ""),
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "snippet": full_message.get("snippet", ""),
                    "raw_body": raw_body,
                    "recipient": headers.get("reply-to") or headers.get("from", ""),
                }
            )
        return normalized, "ok"
    except Exception as exc:
        return [], f"gmail fetch failed: {exc}"


def fetch_free_calendar_slots(days_ahead: int = 3) -> Tuple[List[str], str]:
    """Compute free one-hour slots from Google Calendar free/busy data."""

    _, calendar_service, detail = _build_services()
    if not calendar_service:
        return [], detail

    now_utc = datetime.now(UTC)
    window_end = now_utc + timedelta(days=max(1, days_ahead))

    body = {
        "timeMin": now_utc.isoformat(),
        "timeMax": window_end.isoformat(),
        "items": [{"id": "primary"}],
    }

    try:
        fb = calendar_service.freebusy().query(body=body).execute()
        busy_entries = fb.get("calendars", {}).get("primary", {}).get("busy", [])

        busy_ranges: List[Tuple[datetime, datetime]] = []
        for entry in busy_entries:
            start = datetime.fromisoformat(entry["start"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(entry["end"].replace("Z", "+00:00"))
            busy_ranges.append((start, end))

        slots: List[str] = []
        cursor = now_utc.replace(minute=0, second=0, microsecond=0)
        if cursor < now_utc:
            cursor += timedelta(hours=1)

        while cursor < window_end and len(slots) < 6:
            if 9 <= cursor.hour <= 16:
                slot_end = cursor + timedelta(hours=1)
                overlaps = any(not (slot_end <= b_start or cursor >= b_end) for b_start, b_end in busy_ranges)
                if not overlaps:
                    slots.append(cursor.astimezone().strftime("%A at %H:%M %Z"))
            cursor += timedelta(hours=1)

        if not slots:
            return [], "no free slots in selected horizon"
        return slots, "ok"
    except Exception as exc:
        return [], f"calendar free/busy fetch failed: {exc}"


def dispatch_email_reply(
    thread_id: str,
    recipient: str,
    subject: str,
    body_text: str,
    message_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """Send a Gmail threaded reply and mark original message as read."""

    gmail_service, _, detail = _build_services()
    if not gmail_service:
        return False, detail

    try:
        msg = MIMEText(body_text)
        msg["to"] = recipient
        msg["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        gmail_service.users().messages().send(
            userId="me",
            body={
                "raw": raw,
                "threadId": thread_id,
            },
        ).execute()

        if message_id:
            gmail_service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()

        return True, "email reply sent"
    except Exception as exc:
        return False, f"gmail reply dispatch failed: {exc}"
