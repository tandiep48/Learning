"""
entity/query_schemas.py
-----------------------
Shared Pydantic v2 building blocks for the admin "list" endpoints, whose filters
now travel in a validated JSON body (POST .../query) instead of the query string.

- PaginatedQuery: the page/page_size base every list model inherits, with
  extra keys forbidden so a typo'd filter fails loudly.
- TrimmedStr / HskLevel: reusable optional string field types that trim input
  and collapse a blank value to None (no filter).
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

# Same set the service layer validates create/update against.
HSK_LEVELS = {f"HSK{n}" for n in range(1, 7)}


def _blank_to_none(value):
    """Trim a string, and treat an empty/whitespace value as 'not provided'."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _known_hsk_level(value):
    if value is not None and value not in HSK_LEVELS:
        raise ValueError(f"must be one of {sorted(HSK_LEVELS)}")
    return value


def trimmed_str(max_length: int):
    """
    An optional filter string that is trimmed, with a blank value collapsed to
    None (no filter), and bounded by `max_length` when present.

    The length bound is attached to the inner `str`, so it is skipped for None
    (a bound on the whole Optional would raise on a blank-collapsed value).
    """
    return Annotated[
        Optional[Annotated[str, StringConstraints(max_length=max_length)]],
        BeforeValidator(_blank_to_none),
    ]


# Optional HSK level ("HSK1".."HSK6"), trimmed, blank -> None, else validated.
HskLevel = Annotated[Optional[str], BeforeValidator(_blank_to_none), AfterValidator(_known_hsk_level)]


class PaginatedQuery(BaseModel):
    """Base for admin list request bodies: 1-based paging, page size capped at 100."""

    # Reject unknown keys so a mistyped filter is a 422, not a silent no-op.
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class LearnerListQuery(BaseModel):
    """
    Base for the learner list/search request bodies.

    The learner reads keep the same POST-body validation as admin, but their
    endpoints already clamp page_size to their own cap (the legacy GET did, and
    the shared helper still does). So the bound here is only a generous sanity
    limit — the vocab-select UI legitimately offers sizes up to 1000 — and the
    real cap stays in the endpoint helper. Subclasses override page_size's
    default to match the endpoint they validate.
    """

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=1000)
