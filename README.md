# 👔 Executive Inbound & Meeting Scheduler Agent

> An autonomous, Human-in-the-Loop (HITL) agentic workflow orchestrating inbound email classification, calendar availability validation, and context-aware response dispatching.

[![Watch Demo Video](https://img.shields.io/badge/Loom-Watch_Live_Demo-625DF5?style=for-the-badge&logo=loom&logoColor=white)](LINK_CATRE_LOOM_AICI)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange?style=for-the-badge)](https://langchain-ai.github.io/langgraph/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red?style=for-the-badge&logo=streamlit)](https://streamlit.io/)

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