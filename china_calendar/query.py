"""Local date queries; unpublished holiday schedules are always explicit."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .events import overlaps
from .models import Event


def event_record(event: Event) -> dict:
    return {
        "uid": event.uid,
        "summary": event.summary,
        "kind": event.kind,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "all_day": type(event.start) is date,
        "description": event.description,
        "url": event.url,
    }


def day_record(root: Path, day: date, groups: dict[str, list[Event]], feed: str) -> dict:
    tomorrow = day + timedelta(days=1)
    lunar = None
    lunar_path = root / "data" / "lunar" / f"{day.year}.json"
    if lunar_path.exists():
        lunar = next(
            (row for row in json.loads(lunar_path.read_text(encoding="utf-8"))["days"]
             if row["date"] == day.isoformat()), None
        )
    holiday_path = root / "data" / "holidays" / f"{day.year}.json"
    notice = json.loads(holiday_path.read_text(encoding="utf-8")) if holiday_path.exists() else {}
    published = bool(notice.get("papers") and notice.get("days"))
    arrangement = next(
        (event for event in groups["holidays"] if overlaps(event, day, tomorrow)), None
    )
    if arrangement:
        published = True
        status = "holiday" if arrangement.kind == "holiday" else "makeup_workday"
    elif published:
        status = "weekend" if day.weekday() >= 5 else "workday"
    else:
        status = "unknown"
    return {
        "date": day.isoformat(),
        "weekday": day.isoweekday(),
        "lunar": lunar,
        "holiday_schedule_published": published,
        "day_type": status,
        "events": [event_record(event) for event in groups[feed] if overlaps(event, day, tomorrow)],
    }


def format_day(record: dict) -> str:
    labels = {
        "holiday": "放假", "makeup_workday": "调休补班", "weekend": "周末",
        "workday": "工作日", "unknown": "该年放假调休安排未收录，不能判断是否补班或放假",
    }
    weekday = "一二三四五六日"[record["weekday"] - 1]
    lines = [f"{record['date']} 星期{weekday} · {labels[record['day_type']]}"]
    lunar = record["lunar"]
    if lunar:
        months = ("正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊")
        lines.append(f"农历：{'闰' if lunar['leap_month'] else ''}{months[lunar['lunar_month'] - 1]}月{lunar['lunar_day']}日")
    else:
        lines.append("农历：本地暂无该年数据")
    for event in record["events"]:
        when = "全天" if event["all_day"] else event["start"][11:16] + " 北京时间"
        lines.append(f"  {when}  {event['summary']}")
    if not record["events"]:
        lines.append("  所选订阅当天无事件")
    return "\n".join(lines)
