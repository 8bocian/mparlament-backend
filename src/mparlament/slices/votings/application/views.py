"""Read-time projection of a ``Voting`` + its ``Vote`` rows into the FE-facing shape (spec §2).

The computed block (spec §2 Voting "computed") is derived here, never stored: counts, turnout, the
``{id,name,club}`` eligible/voted/notVoted lists, and the requester-specific ``hasVoted``/``myVote``.

`myVote` choice (documented per the doc's note next to the code): we surface the **stored/
normalized** value — ``"abstained"`` for an abstention, not ``"abstain"``. The FE treats
``abstain``/``abstained`` equivalently, and casting then reading back stays consistent (the vote
endpoint returns the same normalized value the projection reports here).
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.votings.domain.entities import (
    OPTION_KEYS,
    DirectoryUser,
    Voting,
    Vote,
)


def _person(user: DirectoryUser) -> dict:
    """The ``{id, name, club}`` shape the FE reads in eligible/voted/notVoted lists."""
    return {"id": user.id, "name": user.name, "club": user.club}


def _voting_fields(voting: Voting) -> dict:
    """The persisted Voting fields the FE reads back (option flags flattened to top level)."""
    data = {
        "id": voting.id,
        "title": voting.title,
        "description": voting.description,
        "category": voting.category,
        "startTime": voting.startTime,
        "endTime": voting.endTime,
        "status": voting.status,
        "recipientsType": voting.recipientsType,
        "selectedGroups": list(voting.selectedGroups),
        "selectedMembers": list(voting.selectedMembers),
        "linkedItemType": voting.linkedItemType,
        "linkedItemId": voting.linkedItemId,
        "applicant": voting.applicant,
        "managers": list(voting.managers),
        "attachments": [asdict(a) for a in voting.attachments],
        "createdBy": voting.createdBy,
    }
    # Echo the create-form option flags the FE persisted (spec §2 Voting).
    for key in OPTION_KEYS:
        if key in voting.options:
            data[key] = voting.options[key]
    return data


def build_voting_view(
    voting: Voting,
    votes: list[Vote],
    users: list[DirectoryUser],
    requester_id: int | None,
) -> dict:
    """Merge the persisted Voting fields with the read-time computed block (spec §2)."""
    eligible = voting.eligible_users(users)
    voted_by_user = {v.userId: v.value for v in votes}

    votes_for = sum(1 for v in votes if v.value == "for")
    votes_against = sum(1 for v in votes if v.value == "against")
    abstained = sum(1 for v in votes if v.value == "abstained")

    voted_users = [u for u in eligible if u.id in voted_by_user]
    not_voted_users = [u for u in eligible if u.id not in voted_by_user]

    view = _voting_fields(voting)
    view.update(
        {
            "votesFor": votes_for,
            "votesAgainst": votes_against,
            "abstained": abstained,
            "votedCount": votes_for + votes_against + abstained,
            "totalEligible": len(eligible),
            "eligibleUsers": [_person(u) for u in eligible],
            "votedUsers": [_person(u) for u in voted_users],
            "notVotedUsers": [_person(u) for u in not_voted_users],
            "hasVoted": requester_id in voted_by_user,
            "myVote": voted_by_user.get(requester_id) if requester_id else None,
        }
    )
    return view
