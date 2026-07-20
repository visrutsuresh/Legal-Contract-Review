from datetime import datetime
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel

from app.audit import chain


class Ticket(BaseModel):
    ticket_id: str  # unique id for this ticket
    source: Literal["chat", "form", "email", "voice_transcript", "jira"]  # only these exact strings are allowed as input
    subject: str  # short title
    body: str  # the normalised message text
    customer_id: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    created_at: datetime
    raw: dict = {}  # holds the untouched original payload, in case we need it for audit


class State(TypedDict):
    ticket: Ticket
    classification: dict  # agent 1's work
    routing: dict  # the model-router's choice
    retrieval: dict  # agent 2's KB snippets
    draft: dict  # agent 3's reply
    compliance: dict  # agent 4's pass/fail
    decision: dict  # auto send vs escalate
    review_count: int  # how many times the review gate has run (caps the regen retry)
    audit: Annotated[list, chain]  # append only to make ticket longer
    raw_input: dict  # the messy inbound payload, before intake turns it into a Ticket
    error: str | None  # why the intake rejected this input
    learned: bool  # True if this resolved ticket was filed into the KB
    sensitivity: dict  # PII scan + category heuristic result, set before routing
    difficulty: dict  # LLM difficulty score (simple vs complex)
    messages: list  # conversation turns, oldest first. role = customer | agent | internal
    lifecycle: str  # state of the ticket -open, awaiting_customer, resolved


def public_messages(messages: list) -> list:
    # the customer-safe view of a thread: everything except private internal notes.
    # single source of truth so no customer-facing reader (thread view, reply model) can forget the filter.
    return [m for m in (messages or []) if m["role"] != "internal"]


# confidence policy (shared by both modes so they decide identically).
# NOTE: this is a grounded HEURISTIC, not a calibrated probability. A calibrated
# number needs a labelled batch + a fitted reliability curve (see TODO item 19/42).
CONF_SENSITIVE = 85  # recalibrated 90->85: the heuristic under-rated good answers (a correct billing reply scored 87)
CONF_NORMAL = 60  # everything else


def grounded_confidence(agent_conf, retrieval) -> int:
    # blend the agent's self-reported confidence with how strongly the KB actually matched.
    # both have to be high for a high score: "I'm sure" AND "the KB backs me up".
    top = max((h.get("score", 0) for h in (retrieval or [])), default=0)
    if agent_conf is None:
        return int(top)  # no self-report -> lean on retrieval strength alone
    return round((agent_conf + top) / 2)


def confidence_threshold(category, priority=None) -> int:
    # money categories AND high-priority tickets must clear a higher bar before auto-send
    high_stakes = category in {"refund", "billing"} or priority == "high"
    return CONF_SENSITIVE if high_stakes else CONF_NORMAL
