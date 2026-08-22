from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import Event


CALENDAR_NAMES = {
    "calendar": "中国节假日・纪念日・二十四节气",
    "holidays": "中国大陆节假日与调休",
    "solar-terms": "二十四节气（北京时间）",
    "observances": "中国传统节日与纪念日",
    "supplement": "中国日历补充・精确交节与纪念日",
}

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> list[str]:
    if len(line.encode("utf-8")) <= 75:
        return [line]
    chunks: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        limit = 75 if not chunks else 74
        if len(candidate.encode("utf-8")) > limit:
            chunks.append(current)
            current = char
        else:
            current = candidate
    chunks.append(current)
    return [chunks[0], *(" " + chunk for chunk in chunks[1:])]


def _event_lines(event: Event, dtstamp: str) -> list[str]:
    lines = ["BEGIN:VEVENT", f"UID:{_escape(event.uid)}", f"DTSTAMP:{dtstamp}"]
    if isinstance(event.start, datetime):
        start = event.start.astimezone(SHANGHAI).replace(tzinfo=None)
        end = event.end.astimezone(SHANGHAI).replace(tzinfo=None)  # type: ignore[union-attr]
        lines.extend(
            [
                f"DTSTART;TZID=Asia/Shanghai:{start:%Y%m%dT%H%M%S}",
                f"DTEND;TZID=Asia/Shanghai:{end:%Y%m%dT%H%M%S}",
            ]
        )
    else:
        lines.extend(
            [
                f"DTSTART;VALUE=DATE:{event.start:%Y%m%d}",
                f"DTEND;VALUE=DATE:{event.end:%Y%m%d}",
            ]
        )
    lines.extend(
        [
            f"SUMMARY;LANGUAGE=zh_CN:{_escape(event.summary)}",
            "TRANSP:TRANSPARENT",
            f"CATEGORIES:{','.join(_escape(category) for category in event.categories)}",
        ]
    )
    if event.apple_special_day:
        lines.append(f"X-APPLE-SPECIAL-DAY:{event.apple_special_day}")
    if event.apple_universal_id:
        lines.append(f"X-APPLE-UNIVERSAL-ID:{event.apple_universal_id}")
    if event.description:
        lines.append(f"DESCRIPTION:{_escape(event.description)}")
    if event.url:
        lines.append(f"URL:{event.url}")
    lines.append("END:VEVENT")
    return lines


def render_calendar(name: str, events: list[Event], generated_at: str) -> bytes:
    dt = datetime.fromisoformat(generated_at).astimezone(timezone.utc)
    dtstamp = dt.strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Luke-Lab666//China Calendar 1.0//ZH-CN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CALENDAR_NAMES[name]}",
        "X-WR-TIMEZONE:Asia/Shanghai",
        "X-APPLE-LANGUAGE:zh",
        "X-APPLE-REGION:CN",
        "X-APPLE-CALENDAR-COLOR:#FF9500",
        "COLOR:orange",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Shanghai",
        "X-LIC-LOCATION:Asia/Shanghai",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:CST",
        "DTSTART:19700101T000000",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for event in sorted(
        events, key=lambda item: (item.start.isoformat(), item.summary, item.uid)
    ):
        lines.extend(_event_lines(event, dtstamp))
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in _fold(line)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


def write_calendars(root: Path, groups: dict[str, list[Event]], generated_at: str) -> None:
    output = root / "calendars"
    output.mkdir(parents=True, exist_ok=True)
    for name, events in groups.items():
        content = render_calendar(name, events, generated_at)
        path = output / f"{name}.ics"
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
