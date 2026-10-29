# 📬 Executive Inbound & Meeting Scheduler Agent

> **An autonomous, guardrailed scheduling concierge with LangGraph orchestration, calendar availability validation, and Human-in-the-Loop review.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)
[![Demo Video](https://img.shields.io/badge/YouTube-Watch%20Demo-red?logo=youtube)](https://www.youtube.com/watch?v=bAqVuo0frVw)

---

## 🎯 Executive Summary & Value Proposition

Executive inboxes are inundated with non-actionable emails, newsletters, and scheduling back-and-forth. This agent serves as an autonomous gatekeeper and scheduling co-pilot:

1. **Noise Reduction:** Triages and archives newsletters and non-actionable inbound traffic autonomously.
2. **Intent & Entity Extraction:** Extracts meeting context, company identity, and dates across multiple languages (English & Romanian).
3. **Availability Guardrails:** Validates candidate slots against deterministic calendar availability constraints to prevent double-booking.
4. **Human-in-the-Loop (HITL) Governance:** Empowers leadership to inspect, edit, and approve drafts before physical dispatch via the Gmail API.
5. **Auditable Ledger:** Automatically synchronizes interaction history and executive notes into persistent storage (`meetings_tracker.xlsx`).

---

## 🏛️ System Architecture

```mermaid
graph TD
    A[Gmail Inbound Poller] -->|Raw Payload| B[LangGraph StateGraph]
    B --> C{Triage & Classifier}
    C -->|Newsletter / Cold Spam| D[Archive Node]
    C -->|Meeting / Interview Intent| E[Calendar Skill & Guardrail]
    E --> F[Contextual Response Drafter]
    F --> G[Validation Gatekeeper]
    G --> H[Human-in-the-Loop Review Queue]
    H -->|Approve & Dispatch| I[Gmail API Reply Dispatcher]
    H -->|Reject / Archive| D
    I --> J[Auditable Excel Ledger]
    D --> J