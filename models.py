"""Typed models for the Executive Inbound & Meeting Scheduler Agent."""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field, HttpUrl


class MeetingDetails(BaseModel):
    """Structured extraction result for inbound email content."""

    is_meeting_request: bool = False
    sender_name: str = "Unknown Sender"
    company_or_organization: Optional[str] = None
    topic_or_context: Optional[str] = None
    proposed_slots: List[str] = Field(default_factory=list)
    has_booking_link: bool = False
    booking_url: Optional[HttpUrl] = None


class AgentState(TypedDict):
    """LangGraph state contract for processing one inbound email."""

    email_id: str
    received_timestamp: str
    raw_email_body: str
    extracted_details: Optional[MeetingDetails]
    available_calendar_slots: List[str]
    draft_response: Optional[str]
    validation_passed: bool
    validation_notes: Optional[str]
    status: Literal["Pending Review", "Approved & Sent", "Rejected / Archived", "Archived"]
