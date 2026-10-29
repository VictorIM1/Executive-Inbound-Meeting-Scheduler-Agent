"""Google Workspace service integrations for Gmail inbound and outbound operations."""

import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText
import html
import os
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def get_gmail_service():
    """Autentifică utilizatorul și returnează instanța clientului Gmail API."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("Fișierul credentials.json lipsește din rădăcina proiectului.")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)

        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def get_google_services():
    """Alias retrocompatibil care returnează serviciul Gmail."""
    return get_gmail_service()

def get_mock_calendar_slots() -> list[str]:
    """Generează intervale orare concrete (start - end) pentru zilele lucrătoare."""
    now = datetime.now()
    slots = []
    day_offset = 1

    while len(slots) < 3:
        target_day = now + timedelta(days=day_offset)
        if target_day.weekday() < 5:
            day_name = target_day.strftime("%A")
            ro_days = {
                "Monday": "Luni", "Tuesday": "Marți", "Wednesday": "Miercuri",
                "Thursday": "Joi", "Friday": "Vineri"
            }
            ro_day = ro_days.get(day_name, day_name)

            if len(slots) == 0:
                slots.append(f"{ro_day} între 11:00 - 11:45 EET")
            elif len(slots) == 1:
                slots.append(f"{ro_day} între 14:30 - 15:15 EET")
            else:
                slots.append(f"{ro_day} între 16:00 - 16:45 EET")
        day_offset += 1

    return slots

def _decode_gmail_base64(data: str) -> str:
    """Decodare sigură pentru Base64URL fără padding (formatul standard evaziv returnat de Gmail API)."""
    if not data:
        return ""
    data = data.replace("-", "+").replace("_", "/")
    # Adăugăm padding-ul '=' lipsă pentru a preveni binascii.Error
    data += "=" * ((4 - len(data) % 4) % 4)
    try:
        return base64.b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""

def _extract_body_text(payload: dict) -> str:
    """Extrage recursiv corpul text din payload-ul mesajului Gmail."""
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return _decode_gmail_base64(body_data)

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            text = _decode_gmail_base64(part["body"]["data"])
            if text: 
                return text

    for part in parts:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            raw_html = _decode_gmail_base64(part["body"]["data"])
            if raw_html:
                clean_text = re.sub(r"<[^>]+>", " ", raw_html)
                return html.unescape(" ".join(clean_text.split()))

    for part in parts:
        nested_text = _extract_body_text(part)
        if nested_text: 
            return nested_text

    return ""

def fetch_real_emails(gmail_service, max_results: int = 5) -> list[dict]:
    """Extrage mesajele necitite din contul conectat."""
    results = gmail_service.users().messages().list(userId="me", q="is:unread", maxResults=max_results).execute()
    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        detail = gmail_service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        payload = detail.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        body_content = _extract_body_text(payload).strip()
        if not body_content:
            body_content = detail.get("snippet", "")

        emails.append(
            {
                "id": msg["id"],
                "email_id": msg["id"],
                "thread_id": detail.get("threadId", msg["id"]),
                "sender": headers.get("from", "Unknown Sender"),
                "subject": headers.get("subject", "No Subject"),
                "date": headers.get("date", datetime.utcnow().isoformat()),
                "body": body_content,
            }
        )

    return emails

def _extract_pure_email(sender_raw: str) -> str:
    """Extrage strict adresa de email din formatul 'Nume <email>'."""
    match = re.search(r"<([^>]+)>", sender_raw)
    if match:
        return match.group(1).strip()
    return sender_raw.strip()

def dispatch_real_email_reply(gmail_service, to_email: str, subject: str, body_text: str, thread_id: str):
    """Trimite un email ca răspuns pe thread și elimină eticheta UNREAD."""
    clean_to = _extract_pure_email(to_email)
    message = MIMEText(body_text, "plain", "utf-8")
    message["to"] = clean_to
    clean_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message["subject"] = clean_subject

    try:
        thread_detail = gmail_service.users().threads().get(userId="me", id=thread_id).execute()
        first_msg_headers = {
            h["name"].lower(): h["value"]
            for h in thread_detail.get("messages", [{}])[0].get("payload", {}).get("headers", [])
        }
        msg_id_val = first_msg_headers.get("message-id")
        if msg_id_val:
            message["In-Reply-To"] = msg_id_val
            message["References"] = msg_id_val
    except Exception:
        pass

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    payload = {"raw": raw, "threadId": thread_id}

    sent = gmail_service.users().messages().send(userId="me", body=payload).execute()

    try:
        gmail_service.users().messages().modify(userId="me", id=thread_id, body={"removeLabelIds": ["UNREAD"]}).execute()
    except Exception:
        pass

    return sent