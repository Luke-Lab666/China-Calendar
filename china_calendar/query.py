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


def _load_optional(path: Path, cache: dict[Path, dict] | None) -> dict:
    if cache is not None and path in cache:
        return cache[path]
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if cache is not None:
        cache[path] = payload
    return payload


def day_record(
    root: Path, day: date, groups: dict[str, list[Event]], feed: str,
    cache: dict[Path, dict] | None = None,
) -> dict:
    """Describe one day. Pass a shared ``cache`` when querying many days."""
    tomorrow = day + timedelta(days=1)
    lunar_payload = _load_optional(root / "data" / "lunar" / f"{day.year}.json", cache)
    lunar = next(
        (row for row in lunar_payload.get("days", []) if row["date"] == day.isoformat()), None
    )
    notice = _load_optional(root / "data" / "holidays" / f"{day.year}.json", cache)
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


def next_holiday(groups: dict[str, list[Event]], today: date) -> dict | None:
    """The nearest published holiday that has not ended; never a prediction."""
    holiday = next(
        (event for event in sorted(groups["holidays"], key=lambda item: item.start)
         if event.kind == "holiday" and event.end > today),
        None,
    )
    if holiday is None:
        return None
    assert isinstance(holiday.start, date) and isinstance(holiday.end, date)
    ongoing = holiday.start <= today
    return {
        "name": holiday.summary.removesuffix("（休）"),
        "start": holiday.start.isoformat(),
        "end": holiday.end.isoformat(),
        "length": (holiday.end - holiday.start).days,
        "ongoing": ongoing,
        "days": (holiday.end - today).days if ongoing else (holiday.start - today).days,
        "url": holiday.url,
    }


def format_next_holiday(record: dict | None) -> str:
    if record is None:
        return "暂无已收录的后续放假安排；下一份正式通知收录前不预测假期。"
    last = date.fromisoformat(record["end"]) - timedelta(days=1)
    span = f"{record['start']} 至 {last.isoformat()}，共 {record['length']} 天"
    if record["ongoing"]:
        remaining = "今天是假期最后一天" if record["days"] == 1 else f"假期还剩 {record['days']} 天（含今天）"
        return f"正在放假：{record['name']}（{span}），{remaining}。"
    countdown = "明天放假" if record["days"] == 1 else f"还有 {record['days']} 天"
    return f"下一个假期：{record['name']}（{span}），{countdown}。"
