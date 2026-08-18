"""Domain entity for the groups slice (spec §2 Group).

``Group`` is a thin read model backing the voting-recipient picker (#41). Groups are the values
``selectedGroups``/``recipientsType="groups"`` resolve against, so a group's ``id`` is kept equal
to the underlying ``User.group`` value (C8) — voting eligibility (doc 05) string-matches the two.
``memberCount`` is the number of ``User``s in the group (FE shows ``group.memberCount || 0``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Group:
    """A recipient group: ``{id, name, memberCount}`` (framework-free, C8)."""

    id: str
    name: str
    memberCount: int = 0
