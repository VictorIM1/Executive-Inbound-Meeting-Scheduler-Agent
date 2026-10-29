"""LangGraph workflow for autonomous inbound meeting triage."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from models import AgentState, MeetingDetails

_CALENDAR_SLOTS = [
    "Miercuri între 11:00 - 11:45 EET",
    "Joi între 14:30 - 15:15 EET",
    "Vineri între 16:00 - 16:45 EET",
]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_booking_url(text: str) -> Optional[str]:
    url_match = re.search(r"https?://[^\s)]+", text)
    if not url_match:
        return None
    url = url_match.group(0).rstrip(".,")
    if any(domain in url.lower() for domain in ("calendly", "hubspot", "savvycal")):
        return url
    return None


def _extract_sender_name(raw_email_body: str) -> str:
    header_match = re.search(r"^From:\s*([^<\n\r]+)", raw_email_body, re.MULTILINE | re.IGNORECASE)
    if header_match:
        name = header_match.group(1).strip().strip('"\'')
        if name and not name.lower().startswith("unknown"):
            return name

    closing = re.search(
        r"(?:cu\s+stim[aă]|cu\s+respect|toate\s+cele\s+bune|best|regards|thanks)[,\s\n]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        raw_email_body,
        re.IGNORECASE,
    )
    if closing:
        return closing.group(1).strip()

    intro_match = re.search(r"(?:from|i am|this is|sunt|aici este)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", raw_email_body, re.IGNORECASE)
    if intro_match:
        return intro_match.group(1).strip()

    return "Unknown Sender"


def _extract_company(raw_email_body: str) -> Optional[str]:
    patterns = [
        r"(?:din cadrul|de la|la|at|from)\s+([A-Z0-9][\w&\-\s]{2,25})",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_email_body, re.IGNORECASE)
        if match:
            value = _normalize_whitespace(match.group(1)).strip(".,\n\r")
            if value.lower() not in {"the", "a", "an", "unui", "unei", "acest", "echipa"}:
                return value
    return None


def _extract_proposed_slots(raw_email_body: str) -> List[str]:
    lowered = raw_email_body.lower()
    extracted: List[str] = []

    if "tomorrow" in lowered or "mâine" in lowered or "maine" in lowered or "miercuri" in lowered:
        extracted.append("Miercuri între 11:00 - 11:45 EET")
    if "thursday" in lowered or "joi" in lowered:
        extracted.append("Joi între 14:30 - 15:15 EET")
    if "friday" in lowered or "vineri" in lowered:
        extracted.append("Vineri între 16:00 - 16:45 EET")

    return extracted


def _is_romanian(text: str) -> bool:
    lowered = text.lower()
    ro_indicators = ["bună", "buna", "ziua", "vă mulțumim", "va multumim", "interviu", "disponibil", "cu stimă", "cu stima"]
    return any(ind in lowered for ind in ro_indicators)


def classify_and_extract(state: AgentState) -> AgentState:
    """Classify inbound text and extract structured meeting attributes."""

    raw = state.get("raw_email_body", "")
    lowered = raw.lower()

    meeting_intent_signals = (
        "meeting", "schedule", "availability", "call", "intro", "connect", "calendar",
        "interviu", "discutie", "discuție", "sedinta", "ședință", "disponibilitate", 
        "disponibilitatea", "intervale orare", "recrutare", "google meet", "convorbire",
    )
    is_meeting_request = any(signal in lowered for signal in meeting_intent_signals)

    booking_url = _extract_booking_url(raw)
    extracted = MeetingDetails(
        is_meeting_request=is_meeting_request,
        sender_name=_extract_sender_name(raw),
        company_or_organization=_extract_company(raw),
        topic_or_context="Technical Interview / Executive inbound" if is_meeting_request else "General inbound",
        proposed_slots=_extract_proposed_slots(raw),
        has_booking_link=booking_url is not None,
        booking_url=booking_url,
    )
    state["extracted_details"] = extracted.model_dump(mode="json")

    if not extracted.is_meeting_request:
        state["status"] = "Archived"
    return state


def calendar_skill(state: AgentState) -> AgentState:
    """Populate available calendar slots from a deterministic calendar skill."""
<<<<<<< Updated upstream

    existing_slots = state.get("available_calendar_slots", [])
    state["available_calendar_slots"] = list(existing_slots or _CALENDAR_SLOTS)
=======
    state["available_calendar_slots"] = list(_CALENDAR_SLOTS)
>>>>>>> Stashed changes
    return state


def draft_reply(state: AgentState) -> AgentState:
    """Create reply draft based on extracted meeting details and availability."""

    details = _details_from_state(state.get("extracted_details"))
    if not details:
        state["draft_response"] = ""
        return state

    sender = details.sender_name or "there"
    is_ro = _is_romanian(state.get("raw_email_body", ""))

    if details.has_booking_link and details.booking_url:
        if is_ro:
            state["draft_response"] = (
                f"Bună ziua,\n\n"
                f"Vă mulțumesc pentru linkul de programare ({details.booking_url}). "
                "Voi alege un interval direct prin intermediul acestuia.\n\n"
                "Cu stimă,\nVictor Ionescu"
            )
        else:
            state["draft_response"] = (
                f"Hi {sender},\n\n"
                f"Thank you for sharing your scheduling link ({details.booking_url}). "
                "I will reserve the slot directly through that link.\n\n"
                "Best regards,\nVictor Ionescu"
            )
        return state

    available = state.get("available_calendar_slots", [])
    proposed = details.proposed_slots

    if proposed:
        overlap = [slot for slot in proposed if slot in available]
        if overlap:
            slot_list = ", ".join(overlap)
            if is_ro:
                state["draft_response"] = (
                    f"Bună ziua,\n\n"
                    f"Vă mulțumesc pentru mesaj. Următoarele intervale propuse sunt perfecte: {slot_list}. "
                    "Vă rog să-mi confirmați care dintre ele rămâne stabilit și voi rezerva intervalul în calendar.\n\n"
                    "Cu stimă,\nVictor Ionescu"
                )
            else:
                state["draft_response"] = (
                    f"Hi {sender},\n\n"
                    f"Great to connect. The following proposed times work on my side: {slot_list}. "
                    "Please confirm your preferred option and we will lock it in.\n\n"
                    "Best regards,\nVictor Ionescu"
                )
        else:
            offered = ", ".join(available[:2])
            if is_ro:
                state["draft_response"] = (
                    f"Bună ziua,\n\n"
                    f"Vă mulțumesc pentru propunere. Nu sunt disponibil la orele menționate, "
                    f"însă vă pot propune următoarele opțiuni: {offered}. Vă rog să-mi spuneți dacă vă convine vreuna.\n\n"
                    "Cu stimă,\nVictor Ionescu"
                )
            else:
                state["draft_response"] = (
                    f"Hi {sender},\n\n"
                    "Thank you for sharing those options. I am unavailable for those exact windows, "
                    f"but I can offer: {offered}. Please confirm which slot suits you best.\n\n"
                    "Best regards,\nVictor Ionescu"
                )
        return state

    offered = ", ".join(available[:2])
    if is_ro:
        state["draft_response"] = (
            f"Bună ziua,\n\n"
            f"Vă mulțumesc pentru oportunitate și pentru invitația la interviu. "
            f"Sunt disponibil pentru discuție în următoarele intervale: {offered}. "
            "Aștept detaliile pentru conectare.\n\n"
            "Cu stimă,\nVictor Ionescu"
        )
    else:
        state["draft_response"] = (
            f"Hi {sender},\n\n"
            f"Thank you for reaching out. I can offer the following times for our discussion: {offered}. "
            "Please let me know which one works best for you.\n\n"
            "Best regards,\nVictor Ionescu"
        )
    return state


def validate_draft(state: AgentState) -> AgentState:
    """Defensive guardrail: allow only slots that were explicitly calendar-verified."""

    draft = state.get("draft_response") or ""
    available = state.get("available_calendar_slots", [])

    # Suportă ambele formate pentru reziliență
    slot_pattern = r"(?:Luni|Marți|Miercuri|Joi|Vineri|Tomorrow|Thursday|Friday) între \d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\s*EET"
    referenced_slots = re.findall(slot_pattern, draft)

    invalid = [slot for slot in referenced_slots if slot not in available]
    if invalid:
        state["validation_passed"] = False
        state["validation_notes"] = f"Draft contains non-verified slots: {', '.join(invalid)}"
    else:
        state["validation_passed"] = True
        state["validation_notes"] = "Draft slots fully validated against live availability."

    if state.get("status") != "Archived":
        state["status"] = "Pending Review"
    return state


def archive_non_meeting(state: AgentState) -> AgentState:
    """Finalize non-meeting inbounds without executive action."""

    state["draft_response"] = ""
    state["available_calendar_slots"] = []
    state["validation_passed"] = False
    state["validation_notes"] = "Archived: message did not request a meeting."
    state["status"] = "Archived"
    return state


def _route_after_classify(state: AgentState) -> str:
    details = _details_from_state(state.get("extracted_details"))
    if details and details.is_meeting_request:
        return "calendar_skill"
    return "archive_non_meeting"


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify_and_extract", classify_and_extract)
    graph.add_node("calendar_skill", calendar_skill)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("validate_draft", validate_draft)
    graph.add_node("archive_non_meeting", archive_non_meeting)

    graph.add_edge(START, "classify_and_extract")
    graph.add_conditional_edges(
        "classify_and_extract",
        _route_after_classify,
        {
            "calendar_skill": "calendar_skill",
            "archive_non_meeting": "archive_non_meeting",
        },
    )
    graph.add_edge("calendar_skill", "draft_reply")
    graph.add_edge("draft_reply", "validate_draft")
    graph.add_edge("validate_draft", END)
    graph.add_edge("archive_non_meeting", END)

    return graph.compile(checkpointer=MemorySaver(), interrupt_after=["validate_draft"])


AGENT_GRAPH = _build_graph()


def _details_from_state(value: Any) -> Optional[MeetingDetails]:
    if not value:
        return None
    if isinstance(value, MeetingDetails):
        return value
    if isinstance(value, dict):
        try:
            return MeetingDetails.model_validate(value)
        except Exception:
            return None
    return None


def run_agent(
    email_id: str,
    thread_id: str,
    sender: str,
    recipient: str,
    subject: str,
    received_timestamp: str,
    raw_email_body: str,
    available_calendar_slots: Optional[List[str]] = None,
) -> AgentState:
    """Run one inbound message through the autonomous meeting triage graph."""

    initial_state: AgentState = {
        "email_id": email_id,
        "thread_id": thread_id,
        "sender": sender,
        "recipient": recipient,
        "subject": subject,
        "received_timestamp": received_timestamp,
        "raw_email_body": raw_email_body,
        "extracted_details": None,
        "available_calendar_slots": available_calendar_slots or [],
        "draft_response": None,
        "validation_passed": False,
        "validation_notes": None,
        "status": "Pending Review",
    }

    config = {
        "configurable": {
            "thread_id": f"inbound-{email_id}",
            "run_ts": datetime.now(timezone.utc).isoformat(),
        }
    }
    final_state = AGENT_GRAPH.invoke(initial_state, config=config)
    return final_state


def state_to_tracker_record(state: AgentState) -> Dict[str, str]:
    """Map workflow state to a persistence record consumable by tracker.py."""

    details = _details_from_state(state.get("extracted_details"))
    available = state.get("available_calendar_slots", [])
    selected_or_offered = (
        ", ".join(details.proposed_slots)
        if details and details.proposed_slots
        else ", ".join(available[:2])
    )

    return {
        "email_id": state.get("email_id", ""),
        "thread_id": state.get("thread_id", ""),
        "received_date": state.get("received_timestamp", "")[:10],
<<<<<<< Updated upstream
        "subject": state.get("subject", ""),
        "recipient": state.get("recipient", ""),
        "sender": details.sender_name if details and details.sender_name != "Unknown Sender" else state.get("sender", "Unknown Sender"),
        "company": details.company_or_organization if details else "",
=======
        "sender": details.sender_name if details else "Unknown Sender",
        "company": details.company_or_organization if details and details.company_or_organization else "",
>>>>>>> Stashed changes
        "topic": details.topic_or_context if details else "",
        "status": "Pending Review" if state.get("status") == "Pending Review" else "Rejected / Archived",
        "data_source": "LIVE" if str(state.get("thread_id", "")).strip() else "MOCK",
        "has_booking_link": bool(details.has_booking_link) if details else False,
        "selected_or_offered_slots": selected_or_offered,
        "draft_preview": state.get("draft_response") or "",
        "executive_notes": "",
        "raw_email_body": state.get("raw_email_body", ""),
        "received_timestamp": state.get("received_timestamp", ""),
        "booking_url": str(details.booking_url) if details and details.booking_url else "",
        "validated_slots": ", ".join(available),
        "validation_passed": bool(state.get("validation_passed", False)),
        "validation_notes": state.get("validation_notes") or "",
    }