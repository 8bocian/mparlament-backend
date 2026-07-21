"""Mappers between the votings ORM rows and the framework-free domain objects.

Attachments round-trip through the frozen ``Attachment`` value object; ``apply_voting`` writes them
back as plain JSON (``dataclasses.asdict``) so SQLite's ``JSON`` type can store them. The option
flags live in a single ``options`` JSON blob (opaque passthrough — the FE writes them, never reads
them back per spec §2 Voting).
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.votings.domain.entities import Attachment, Voting, Vote
from mparlament.slices.votings.infrastructure.models import VoteModel, VotingModel


def to_voting(row: VotingModel) -> Voting:
    return Voting(
        id=row.id,
        title=row.title,
        description=row.description,
        category=row.category,
        startTime=row.start_time,
        endTime=row.end_time,
        status=row.status,
        recipientsType=row.recipients_type,
        selectedGroups=list(row.selected_groups or []),
        selectedMembers=list(row.selected_members or []),
        linkedItemType=row.linked_item_type,
        linkedItemId=row.linked_item_id,
        applicant=row.applicant,
        managers=list(row.managers or []),
        attachments=[Attachment(**a) for a in (row.attachments or [])],
        createdBy=row.created_by,
        options=dict(row.options or {}),
    )


def apply_voting(row: VotingModel, voting: Voting) -> None:
    """Copy a domain ``Voting`` onto an ORM row (JSON columns as plain dicts/lists)."""
    row.title = voting.title
    row.description = voting.description
    row.category = voting.category
    row.start_time = voting.startTime
    row.end_time = voting.endTime
    row.status = voting.status
    row.recipients_type = voting.recipientsType
    row.selected_groups = list(voting.selectedGroups)
    row.selected_members = list(voting.selectedMembers)
    row.linked_item_type = voting.linkedItemType
    row.linked_item_id = voting.linkedItemId
    row.applicant = voting.applicant
    row.managers = list(voting.managers)
    row.attachments = [asdict(a) for a in voting.attachments]
    row.created_by = voting.createdBy
    row.options = dict(voting.options)


def to_vote(row: VoteModel) -> Vote:
    return Vote(id=row.id, votingId=row.voting_id, userId=row.user_id, value=row.value)
