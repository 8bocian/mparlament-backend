"""Sessions-slice domain (framework-free) — spec §2 (Session, CurrentSession, Speaker).

Three aggregates plus the value objects the live session is composed of:
- ``CurrentSession`` — the "na żywo" superset object read under both path aliases (C6). Its
  complex members are frozen value objects (``CurrentSpeaker``, ``AgendaPoint``, ``ScheduleItem``).
  ``with_patch`` implements the partial-merge semantics of ``PUT /api/session/current`` (spec #5):
  only the keys the FE sends are overwritten; everything else is left intact.
- ``Session`` — a list row (spec §2 Session, #7): ``{id, name, date, city}`` plus optional FE
  fallback fields.
- ``Speaker`` — the speaker registry entity (#39/#40): ``{id, name, club, role}``. Distinct from
  the ``CurrentSpeaker`` value object embedded in the live session (which also carries ``time``).

Dates/times are kept as the verbatim FE-format strings (C13); the domain does not parse them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

SCHEDULE_STATUSES = frozenset({"done", "active", "waiting", "crossed", "disabled"})


@dataclass(frozen=True)
class CurrentSpeaker:
    """Current speaker on the live session (``{name, club, role, time?}``)."""

    name: str
    club: str | None = None
    role: str | None = None
    time: str | None = None


@dataclass(frozen=True)
class AgendaPoint:
    """Current agenda point (``{number, title, type}``)."""

    number: str | None = None
    title: str | None = None
    type: str | None = None


@dataclass(frozen=True)
class ScheduleItem:
    """One schedule row (``{time, title, status}``); status from the allowed set."""

    time: str | None = None
    title: str | None = None
    status: str = "waiting"

    def __post_init__(self) -> None:
        if self.status not in SCHEDULE_STATUSES:
            raise ValueError(
                f"Unknown schedule status {self.status!r}; "
                f"allowed: {sorted(SCHEDULE_STATUSES)}"
            )


def _to_speaker(value: object) -> CurrentSpeaker | None:
    if value is None or isinstance(value, CurrentSpeaker):
        return value  # type: ignore[return-value]
    return CurrentSpeaker(**dict(value))  # type: ignore[arg-type]


def _to_point(value: object) -> AgendaPoint | None:
    if value is None or isinstance(value, AgendaPoint):
        return value  # type: ignore[return-value]
    return AgendaPoint(**dict(value))  # type: ignore[arg-type]


def _to_schedule(value: object) -> list[ScheduleItem]:
    items: list[ScheduleItem] = []
    for raw in value or []:  # type: ignore[union-attr]
        items.append(raw if isinstance(raw, ScheduleItem) else ScheduleItem(**dict(raw)))
    return items


@dataclass
class CurrentSession:
    """The live sitting — superset object served under #4 and #6 (C6)."""

    id: int = 1
    title: str = ""
    status: str = ""
    active: bool = False
    date: str | None = None
    start: str | None = None
    startTime: str | None = None
    end: str | None = None
    endTime: str | None = None
    currentSpeaker: CurrentSpeaker | None = None
    currentPoint: AgendaPoint | None = None
    schedule: list[ScheduleItem] = field(default_factory=list)
    zoContent: str = ""

    def __post_init__(self) -> None:
        # Coerce dict/list inputs (e.g. from JSON persistence) into value objects.
        self.currentSpeaker = _to_speaker(self.currentSpeaker)
        self.currentPoint = _to_point(self.currentPoint)
        self.schedule = _to_schedule(self.schedule)

    _VO_FIELDS = {
        "currentSpeaker": _to_speaker,
        "currentPoint": _to_point,
        "schedule": _to_schedule,
    }

    def with_patch(self, patch: dict) -> "CurrentSession":
        """Return a copy with only ``patch``'s keys overwritten (partial PUT, spec #5)."""
        changes: dict[str, object] = {}
        for key, value in patch.items():
            if key not in self.__dataclass_fields__ or key.startswith("_"):
                continue  # ignore unknown keys the FE may send
            coerce = self._VO_FIELDS.get(key)
            changes[key] = coerce(value) if coerce else value
        return replace(self, **changes)


@dataclass
class Session:
    """A session-list row (spec §2 Session, #7). Optional fields are FE fallbacks."""

    id: int
    name: str
    date: str | None = None
    city: str | None = None
    number: str | None = None
    start: str | None = None
    startTime: str | None = None
    end: str | None = None
    endTime: str | None = None


@dataclass
class Speaker:
    """Speaker registry entity (#39/#40). ``id`` is assigned on persistence."""

    id: int | None
    name: str
    club: str | None = None
    role: str | None = None
