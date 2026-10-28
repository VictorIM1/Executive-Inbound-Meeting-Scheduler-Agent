# Executive Inbound & Meeting Scheduler Agent

Production-style technical interview demo for an autonomous inbound triage system with a Human-in-the-Loop (HITL) executive review inbox.

## Features

- Autonomous background polling with APScheduler (configurable interval).
- LangGraph state workflow with deterministic extraction, drafting, and guardrail validation.
- Defensive validation to ensure draft slots only reference verified free calendar slots.
- Streamlit executive dashboard for approving/rejecting queued actions.
- Excel-backed tracker (`meetings_tracker.xlsx`) with pandas in-memory fallback.

## Project Structure

- `models.py`: Pydantic models and typed graph state.
- `agent.py`: LangGraph pipeline and guardrail node.
- `tracker.py`: Excel persistence helpers and review queue operations.
- `scheduler.py`: Autonomous background poller + mock inbox.
- `app.py`: Streamlit HITL dashboard.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Operating Flow

1. Background scheduler ingests mock inbound messages.
2. Agent classifies meeting intent, checks deterministic availability, drafts response.
3. Guardrail validates all mentioned slots against known available slots.
4. Valid meeting inbounds are queued as **Pending Review**.
5. Executive approves/edits/rejects from Streamlit action queue.
