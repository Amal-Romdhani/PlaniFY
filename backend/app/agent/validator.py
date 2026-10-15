from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any


TRIVIAL_VALUES = frozenset({"0", "1"})
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_FRENCH_DATE = re.compile(
    r"\b(\d{1,2})\s+"
    r"(janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    r"septembre|octobre|novembre|décembre|decembre)\s+(\d{4})\b",
    re.IGNORECASE,
)
_SLASH_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
_DAYS = re.compile(r"(?<![\w-])([+-]?\d+(?:[.,]\d+)?)\s*(?:jours?|j)\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w-])([+-]?\d+(?:[.,]\d+)?)(?![\w-])")
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    unverified_values: list[str]
    checked_values: list[str]


def _date_token(value: date) -> str:
    return value.isoformat()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    match = _SLASH_DATE.fullmatch(value)
    if match:
        day, month, year = (int(part) for part in value.split("/"))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = _FRENCH_DATE.fullmatch(value)
    if match:
        day, month, year = match.groups()
        try:
            return date(int(year), _MONTHS[month.lower()], int(day))
        except ValueError:
            return None
    return None


def _normal_values(value: Any) -> set[str]:
    if isinstance(value, date):
        return {_date_token(value)}
    if isinstance(value, bool):
        return set()
    if isinstance(value, (int, float)):
        return {str(value).lower().rstrip("0").rstrip(".") if isinstance(value, float) else str(value)}
    if isinstance(value, dict):
        result: set[str] = set()
        for key, child in value.items():
            result.update(_normal_values(key))
            result.update(_normal_values(child))
        return result
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for child in value:
            result.update(_normal_values(child))
        return result
    if not isinstance(value, str):
        return set()
    result = set()
    for match in _UUID.finditer(value):
        result.add(match.group(0).lower())
    for match in _ISO_DATE.finditer(value):
        parsed = _parse_date(match.group(0))
        if parsed:
            result.add(_date_token(parsed))
    for match in _SLASH_DATE.finditer(value):
        parsed = _parse_date(match.group(0))
        if parsed:
            result.add(_date_token(parsed))
    for match in _FRENCH_DATE.finditer(value):
        parsed = _parse_date(match.group(0))
        if parsed:
            result.add(_date_token(parsed))
    for match in _DAYS.finditer(value):
        result.add(_number_token(match.group(1)))
    for match in _NUMBER.finditer(value):
        result.add(_number_token(match.group(1)))
    return result


def _number_token(value: str) -> str:
    normalized = value.replace(",", ".")
    if normalized.startswith("+"):
        normalized = normalized[1:]
    try:
        number = float(normalized)
    except ValueError:
        return normalized
    return str(int(number)) if number.is_integer() else str(number)


def _text_values(text: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    consumed: list[tuple[int, int]] = []

    def add(raw: str, normalized: str, start: int, end: int) -> None:
        if any(start >= left and end <= right for left, right in consumed):
            return
        values.append((raw, normalized))
        consumed.append((start, end))

    for pattern in (_ISO_DATE, _SLASH_DATE, _FRENCH_DATE):
        for match in pattern.finditer(text):
            parsed = _parse_date(match.group(0))
            if parsed:
                add(match.group(0), _date_token(parsed), match.start(), match.end())
    for match in _DAYS.finditer(text):
        add(match.group(0), _number_token(match.group(1)), match.start(), match.end())
    for match in _UUID.finditer(text):
        add(match.group(0), match.group(0).lower(), match.start(), match.end())
    for match in _NUMBER.finditer(text):
        if (
            (match.start() and text[match.start() - 1] in ".)")
            or (match.end() < len(text) and text[match.end()] in ".)")
        ):
            continue
        if any(match.start() >= left and match.end() <= right for left, right in consumed):
            continue
        normalized = _number_token(match.group(1))
        if normalized in TRIVIAL_VALUES:
            continue
        add(match.group(0), normalized, match.start(), match.end())
    return values


def validate_explanation(text: str, tool_results: list[dict]) -> ValidationResult:
    """Vérifie que les valeurs de l'explication proviennent des outils."""

    allowed: set[str] = set()
    for result in tool_results:
        allowed.update(_normal_values(result))
    checked: list[str] = []
    unverified: list[str] = []
    for raw, normalized in _text_values(text):
        if normalized in allowed or normalized in TRIVIAL_VALUES:
            checked.append(raw)
        else:
            unverified.append(raw)
    return ValidationResult(not unverified, unverified, checked)
