"""Votings-slice domain (framework-free) — spec §2 (Voting, Vote), §6.1.5-6, §8.4.

Two aggregates plus a value object and the pure domain services the slice needs:

- ``Voting`` — the głosowanie aggregate. Carries the persisted fields the FE writes (spec §2
  Voting) and exposes the pure lifecycle/eligibility behaviour the use cases orchestrate:
  ``eligible_users`` resolves recipients per ``recipientsType`` (C8), ``activate``/``archive``
  set the authoritative ``status`` (C15). Computed stats (votesFor/…) are **not** stored — a
  read-time projection derives them from ``Vote`` rows (see ``application/views.py``).
- ``Vote`` — a single cast vote ``{id, votingId, userId, value}`` with ``value`` normalized to the
  canonical ``for|against|abstained`` (C4).
- ``Attachment`` — the ``{id, name, size, type, uploadDate}`` metadata value object (#15).
- ``DirectoryUser`` — the lightweight ``{id, name, club, group}`` view of a voter used for
  eligibility + the ``{id,name,club}`` expansion the FE reads (supplied via the ``UserDirectory``
  port so the slice never imports another slice's ORM).

``normalize_vote`` is the single source of truth for the abstain-enum reconciliation (C4): the FE
button sends ``"abstain"`` while storage/stats use ``"abstained"``.

Dates/times are kept as verbatim FE-format strings (C13); the domain does not parse them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from mparlament.shared.domain import ValidationError

# --- vote enum (C4) --------------------------------------------------------

VALID_VOTES = frozenset({"for", "against", "abstained"})


def normalize_vote(raw: object) -> str:
    """Reconcile the FE/storage abstain enum (C4).

    Accepts ``for``/``against``/``abstain``/``abstained``; maps ``abstain → abstained`` and
    leaves the others unchanged. Anything else raises :class:`ValidationError` (422).
    """
    value = str(raw).strip().lower()
    if value == "abstain":
        value = "abstained"
    if value not in VALID_VOTES:
        raise ValidationError(f"Nieprawidłowy głos: {raw!r}")
    return value


# --- value objects ---------------------------------------------------------


@dataclass(frozen=True)
class Attachment:
    """Voting attachment metadata (spec §2 Voting, #15). ``id`` may be str or int."""

    name: str
    id: str | int | None = None
    size: int | None = None
    type: str | None = None
    uploadDate: str | None = None


@dataclass(frozen=True)
class DirectoryUser:
    """A voter as the FE reads it in eligible/voted lists (``{id, name, club}``) plus ``group``.

    ``group`` drives ``recipientsType="groups"`` eligibility (C8); it is not serialized to the FE.
    """

    id: int
    name: str
    club: str | None = None
    group: str | None = None


def _to_attachment(value: object) -> Attachment:
    if isinstance(value, Attachment):
        return value
    return Attachment(**dict(value))  # type: ignore[arg-type]


# --- entities --------------------------------------------------------------

# Create-form option flags the FE sends but does not read back (persist as-is, spec §2 Voting).
OPTION_KEYS = (
    "quorumRequired",
    "majorityType",
    "allowAbstain",
    "isAnonymous",
    "requireComment",
    "canChangeVote",
    "showResultsDuringVoting",
    "notifyEmail",
    "notifyPush",
)

_RECIPIENTS = frozenset({"all", "groups", "members"})


@dataclass
class Voting:
    """The głosowanie aggregate (spec §2 Voting). Times/status are strings (C13/C15)."""

    id: int | None = None
    title: str = ""
    description: str | None = None
    category: str = "other"  # resolution|amendment|law|budget|committee|other
    startTime: str | None = None  # ISO 8601 / datetime-local (C13)
    endTime: str | None = None
    status: str = "upcoming"  # active|finished|upcoming|archived (C15)
    recipientsType: str = "all"  # all|groups|members (individual→members, C8)
    selectedGroups: list = field(default_factory=list)
    selectedMembers: list = field(default_factory=list)
    linkedItemType: str = "none"  # none|resolution|amendment
    linkedItemId: str | None = None  # stored as string (polymorphic)
    applicant: str | None = None
    managers: list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    createdBy: str | None = None
    options: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # C8: the FE sometimes sends "individual"; the canonical stored value is "members".
        if self.recipientsType == "individual":
            self.recipientsType = "members"
        self.attachments = [_to_attachment(a) for a in self.attachments]
        if self.linkedItemId is not None:
            self.linkedItemId = str(self.linkedItemId)

    # --- eligibility (C8) --------------------------------------------------

    def eligible_users(self, users: list[DirectoryUser]) -> list[DirectoryUser]:
        """Resolve the eligible voters from the full directory per ``recipientsType`` (C8)."""
        if self.recipientsType == "groups":
            wanted = {str(g) for g in self.selectedGroups}
            return [u for u in users if u.group is not None and str(u.group) in wanted]
        if self.recipientsType == "members":
            wanted = {int(m) for m in self.selectedMembers}
            return [u for u in users if u.id in wanted]
        # "all" (and any unexpected value) → everyone (spec §6.1.6).
        return list(users)

    # --- lifecycle (C15) ---------------------------------------------------

    def activate(
        self,
        startTime: str | None = None,
        endTime: str | None = None,
        duration: object = None,  # noqa: ARG002 - accepted from FE, not persisted separately
        delay: object = None,  # noqa: ARG002
    ) -> None:
        """Authoritatively set ``status="active"`` and the times the FE provided (spec #13)."""
        if startTime is not None:
            self.startTime = startTime
        if endTime is not None:
            self.endTime = endTime
        self.status = "active"

    def archive(self) -> None:
        """Authoritatively set ``status="archived"`` (spec #14, C15)."""
        self.status = "archived"

    def with_changes(self, **changes: object) -> "Voting":
        """Return a copy with the given fields overwritten (used by update, spec #11)."""
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass
class Vote:
    """A single cast vote (spec §2 Vote). ``value`` is normalized on construction (C4)."""

    votingId: int
    userId: int
    value: str
    id: int | None = None

    def __post_init__(self) -> None:
        self.value = normalize_vote(self.value)
