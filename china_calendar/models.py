from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


EventKind = Literal[
    "holiday",
    "workday",
    "solar_term",
    "observance",
    "traditional",
    "seasonal",
    "health",
]
AppleSpecialDay = Literal["WORK-HOLIDAY", "ALTERNATE-WORKDAY"]


@dataclass(frozen=True, slots=True)
class Event:
    uid: str
    summary: str
    kind: EventKind
    start: date | datetime
    end: date | datetime
    description: str = ""
    url: str = ""
    categories: tuple[str, ...] = field(default_factory=tuple)
    apple_special_day: AppleSpecialDay | None = None
    apple_universal_id: str = ""
