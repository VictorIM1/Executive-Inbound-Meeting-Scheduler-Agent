"""Streamlit HITL dashboard for executive inbound meeting scheduling."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from scheduler import scheduler_status, start_background_scheduler, trigger_immediate_run
from tracker import (
    get_pending_reviews,
    init_tracker,
    load_all_records,
    to_record_dicts,
    update_status_and_notes,
)

st.set_page_config(page_title="Executive Inbound & Meeting Scheduler Agent", layout="wide")
st.title("Executive Inbound & Meeting Scheduler Agent")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"streamlit-{int(datetime.now(timezone.utc).timestamp())}"

if "scheduler_started" not in st.session_state:
    start_background_scheduler(interval_seconds=30)
    st.session_state.scheduler_started = True

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now(timezone.utc).isoformat()

init_tracker()
records = load_all_records()

status_text = "🟢 Autonomous Background Poller: Active (Scheduled 2x/Day)"
if scheduler_status() != "Active":
    status_text = "🟡 Autonomous Background Poller: Inactive"

total_processed = int(len(records.index))
pending_count = int((records["status"].astype(str) == "Pending Review").sum()) if not records.empty else 0
auto_archived_count = int((records["status"].astype(str) == "Rejected / Archived").sum()) if not records.empty else 0

st.markdown(status_text)
col1, col2, col3 = st.columns(3)
col1.metric("Total Inbound Processed", total_processed)
col2.metric("Pending Executive Approval", pending_count)
col3.metric("Auto-Archived Non-Meetings", auto_archived_count)

with st.sidebar:
    st.subheader("Operations")
    if st.button("Simulate Scheduled Inbound Run", use_container_width=True):
        processed = trigger_immediate_run()
        st.session_state.last_refresh = datetime.now(timezone.utc).isoformat()
        if processed:
            st.success(f"Processed inbound: {processed[0]['email_id']}")
        else:
            st.info("No new inbox messages were available.")

    st.caption(f"Session thread: {st.session_state.thread_id}")
    st.caption(f"Last refresh: {st.session_state.last_refresh}")

review_tab, ledger_tab = st.tabs(["Action Queue (Human-in-the-Loop Review)", "Inbound Ledger & Executive Notes"])

with review_tab:
    pending = get_pending_reviews()
    pending_records = to_record_dicts(pending)

    if not pending_records:
        st.info("No pending items. Autonomous scheduler will queue new review tasks automatically.")
    else:
        choices = [f"{rec['email_id']} | {rec['sender']} | {rec['received_date']}" for rec in pending_records]
        selected_label = st.selectbox("Select queued item", choices)
        selected = pending_records[choices.index(selected_label)]

        left, right = st.columns([1, 1])
        with left:
            st.subheader("Raw Inbound Message")
            st.write(f"**Sender:** {selected.get('sender', 'Unknown Sender')}")
            st.write(f"**Received:** {selected.get('received_timestamp', '')}")
            st.text_area(
                "Message Body",
                value=str(selected.get("raw_email_body", "")),
                disabled=True,
                height=180,
                key=f"raw-{selected['email_id']}",
            )

            st.subheader("Extracted Metadata")
            st.write(f"**Topic:** {selected.get('topic', '') or 'N/A'}")
            st.write(f"**Company:** {selected.get('company', '') or 'N/A'}")
            link = selected.get("booking_url", "")
            st.write(f"**Booking Link Detected:** {'Yes' if bool(link) else 'No'}")
            if link:
                st.write(link)

        with right:
            st.subheader("Calendar & Guardrail")
            st.write(f"**Verified Free Calendar Slots:** {selected.get('validated_slots', '') or 'N/A'}")
            valid = str(selected.get("validation_passed", "")).lower() in {"true", "1"}
            if valid:
                st.success("✅ Validated against live calendar")
            else:
                st.warning("⚠️ Validation failed or not applicable")
            st.caption(selected.get("validation_notes", ""))

            edited_draft = st.text_area(
                "Editable Draft Response",
                value=str(selected.get("draft_preview", "")),
                height=210,
                key=f"draft-{selected['email_id']}",
            )
            notes = st.text_input("Executive Notes", value=str(selected.get("executive_notes", "")), key=f"note-{selected['email_id']}")

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("Approve & Dispatch", use_container_width=True):
                    update_status_and_notes(selected["email_id"], "Approved & Sent", notes, edited_draft)
                    st.success("Item approved and marked as sent.")
                    st.rerun()
            with action_col2:
                if st.button("Reject / Archive", use_container_width=True):
                    update_status_and_notes(selected["email_id"], "Rejected / Archived", notes, edited_draft)
                    st.info("Item archived.")
                    st.rerun()

with ledger_tab:
    st.subheader("Inbound Ledger")
    ledger_df = load_all_records()
    editable_columns = [
        "email_id",
        "received_date",
        "sender",
        "company",
        "topic",
        "status",
        "has_booking_link",
        "selected_or_offered_slots",
        "draft_preview",
        "executive_notes",
    ]
    display_df = ledger_df[editable_columns].copy() if not ledger_df.empty else pd.DataFrame(columns=editable_columns)

    edited_df = st.data_editor(display_df, use_container_width=True, num_rows="fixed")

    if st.button("Save Ledger Edits"):
        for _, row in edited_df.iterrows():
            email_id = str(row.get("email_id", "")).strip()
            if not email_id:
                continue
            update_status_and_notes(
                email_id=email_id,
                new_status=str(row.get("status", "Pending Review")),
                notes=str(row.get("executive_notes", "")),
                final_draft=str(row.get("draft_preview", "")),
            )
        st.success("Ledger edits saved.")
