"""Pure domain services for the amendments slice.

``detect_all_conflicts`` ports the FE's ``detectAllConflicts`` (see front's
``src/mocks/handlers.js``) to Python: given a list of amendments of the same
resolution, it computes, for each amendment, the ids of amendments that *conflict*
(a substantive contradiction) and those that are *potential* conflicts (same area).
"""

from __future__ import annotations

from dataclasses import dataclass

from mparlament.slices.amendments.domain.entities import Amendment


@dataclass(frozen=True)
class _Target:
    article: str | int | None
    section: str
    fragment: str | None


@dataclass(frozen=True)
class _Comparison:
    conflict: bool
    potential: bool
    reason: str | None
    fragment: str | None


def _extract_target(amendment: Amendment) -> _Target:
    """FE parity: ``target`` may be absent — fall back to ``changes[0].before`` for the fragment."""
    target = amendment.target
    if isinstance(target, dict):
        article = target.get("article")
        section = target.get("section") or "other"
        fragment = target.get("fragment")
    else:
        article = None
        section = "other"
        fragment = None

    if fragment is None and amendment.changes:
        first_before = amendment.changes[0].before
        fragment = first_before or None

    return _Target(article=article, section=section, fragment=fragment)


def _compare(a1: Amendment, a2: Amendment) -> _Comparison:
    """Pure port of the FE's ``compareAmendments`` (see mocks/handlers.js)."""
    if a1.resolutionId != a2.resolutionId:
        return _Comparison(False, False, None, None)

    t1 = _extract_target(a1)
    t2 = _extract_target(a2)

    same_fragment = bool(t1.fragment and t2.fragment and t1.fragment == t2.fragment)
    same_article = bool(
        t1.article is not None and t2.article is not None and t1.article == t2.article
    )
    same_section = t1.section == t2.section and t1.section != "other"

    if same_fragment:
        before1 = a1.changes[0].before if a1.changes else ""
        before2 = a2.changes[0].before if a2.changes else ""
        after1 = a1.changes[0].after if a1.changes else ""
        after2 = a2.changes[0].after if a2.changes else ""
        if before1 == before2 and after1 != after2:
            return _Comparison(
                True,
                False,
                f"Zmiana tego samego fragmentu artykułu {t1.article}",
                t1.fragment,
            )

    if same_article and same_section:
        return _Comparison(
            True,
            False,
            f"Zmiana tego samego artykułu {t1.article} w obszarze {t1.section}",
            f"Artykuł {t1.article}",
        )

    if same_section and not same_article:
        return _Comparison(
            False,
            True,
            f"Poprawki dotyczą tego samego obszaru: {t1.section}",
            f"Obszar: {t1.section}",
        )

    if same_article and not same_section:
        return _Comparison(
            False,
            True,
            f"Poprawki dotyczą tego samego artykułu {t1.article}",
            f"Artykuł {t1.article}",
        )

    return _Comparison(False, False, None, None)


def detect_all_conflicts(amendments: list[Amendment]) -> list[dict]:
    """Port of the FE's ``detectAllConflicts`` (returns a new list of dicts)."""
    from mparlament.slices.amendments.application.views import amendment_dict

    result = []
    for a in amendments:
        d = amendment_dict(a)
        d["conflictsWith"] = []
        d["potentialConflicts"] = []
        d["conflictReason"] = None
        d["conflictFragment"] = None
        result.append(d)

    for i in range(len(result)):
        for j in range(i + 1, len(result)):
            comparison = _compare(amendments[i], amendments[j])
            if comparison.conflict:
                if result[j]["id"] not in result[i]["conflictsWith"]:
                    result[i]["conflictsWith"].append(result[j]["id"])
                    result[i]["conflictReason"] = comparison.reason
                    result[i]["conflictFragment"] = comparison.fragment
                if result[i]["id"] not in result[j]["conflictsWith"]:
                    result[j]["conflictsWith"].append(result[i]["id"])
                    result[j]["conflictReason"] = comparison.reason
                    result[j]["conflictFragment"] = comparison.fragment
            elif comparison.potential:
                if result[j]["id"] not in result[i]["potentialConflicts"]:
                    result[i]["potentialConflicts"].append(result[j]["id"])
                if result[i]["id"] not in result[j]["potentialConflicts"]:
                    result[j]["potentialConflicts"].append(result[i]["id"])

    return result
