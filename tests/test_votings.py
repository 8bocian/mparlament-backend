"""Slice 05 — votings (głosowania): lifecycle, cast votes, computed live stats, attachments.

Shapes come verbatim from BACKEND_SPEC.md §4 (#8-#16), §2 (Voting, Vote) + CONVENTIONS C3
(MANAGE_VOTINGS + managers), C4 (abstain normalize), C8 (recipients incl. individual→members),
C10 (bare array #8, computed shapes), C13 (time strings), C15 (authoritative status).

Layering (CLAUDE.md): domain unit → application use-case → API integration. The domain tests
exercise ``normalize_vote`` and eligibility directly; the application tests cover the archive
linked-item cascade with a fake updater (the resolutions slice is not built yet — loose coupling
by id, README); the API tests mirror the doc's TDD checklist.
"""

from __future__ import annotations

import pytest

from mparlament.shared.domain import ValidationError
from mparlament.slices.votings.domain.entities import (
    DirectoryUser,
    Voting,
    normalize_vote,
)

pytestmark = pytest.mark.anyio


# --- domain unit: normalize_vote (checklist #1) ----------------------------


def test_normalize_vote_maps_abstain() -> None:
    assert normalize_vote("abstain") == "abstained"
    assert normalize_vote("abstained") == "abstained"
    assert normalize_vote("for") == "for"
    assert normalize_vote("against") == "against"


def test_normalize_vote_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        normalize_vote("maybe")


# --- domain unit: eligibility (checklist #2-4, C8) -------------------------

_USERS = [
    DirectoryUser(id=1, name="Admin", club="TEST", group=None),
    DirectoryUser(id=2, name="Anna", club="KO", group="A"),
    DirectoryUser(id=3, name="Piotr", club="PiS", group="B"),
]


def test_eligibility_all() -> None:  # checklist #2
    voting = Voting(id=1, title="V", recipientsType="all")
    assert {u.id for u in voting.eligible_users(_USERS)} == {1, 2, 3}


def test_eligibility_members_and_individual() -> None:  # checklist #3
    members = Voting(id=1, title="V", recipientsType="members", selectedMembers=[2, 3])
    assert {u.id for u in members.eligible_users(_USERS)} == {2, 3}
    # "individual" normalizes to "members" on construction (C8) and resolves identically.
    individual = Voting(
        id=1, title="V", recipientsType="individual", selectedMembers=[2, 3]
    )
    assert individual.recipientsType == "members"
    assert {u.id for u in individual.eligible_users(_USERS)} == {2, 3}


def test_eligibility_groups() -> None:  # checklist #4
    voting = Voting(id=1, title="V", recipientsType="groups", selectedGroups=["A"])
    assert {u.id for u in voting.eligible_users(_USERS)} == {2}
