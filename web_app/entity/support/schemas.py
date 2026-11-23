"""
entity/support/schemas.py
-------------------------
Pydantic v2 request models for the support endpoints.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

from entity.query_schemas import PaginatedQuery, trimmed_str

STATUSES = ("open", "resolved")
ITEM_TYPES = (
    "vocab", "passage", "passage_line", "question", "grammar_rule", "grammar_context", "book",
)

Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Body
    item_type: Optional[Literal[ITEM_TYPES]] = None
    item_id: Optional[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = None
    page_url: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]] = None


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Body


class TicketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[Literal[STATUSES]] = None
    # 0 / null clears the assignee; omit the key to leave it unchanged.
    assignee_id: Optional[int] = Field(default=None, ge=0)


class MyTicketsQuery(PaginatedQuery):
    pass


class TicketQuery(PaginatedQuery):
    status: Optional[Literal[STATUSES]] = None
    search: trimmed_str(100) = None
