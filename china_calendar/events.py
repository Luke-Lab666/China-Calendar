from __future__ import annotations

import calendar
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .models import Event


SHANGHAI = ZoneInfo("Asia/Shanghai")

TRADITIONAL_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (2, 2): "龙抬头",
    (3, 3): "上巳节",
    (5, 5): "端午节",
    (7, 7): "七夕",
    (7, 15): "中元节",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
    (12, 23): "北方小年",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _uid(kind: str, day_or_stamp: str, name: str) -> str:
    safe_name = "".join(ch for ch in name if ch.isascii() and ch.isalnum()) or name.encode().hex()
    return f"{kind}-{day_or_stamp}-{safe_name}@china-calendar.luke-lab666"


def holiday_events(root: Path, today: date, future_only: bool) -> list[Event]:
    result: list[Event] = []
    for path in sorted((root / "data" / "holidays").glob("*.json")):
        payload = _load_json(path)
        if not payload["papers"]:
            continue
        source_url = payload["papers"][0]
        for item in payload["days"]:
            event_date = date.fromisoformat(item["date"])
            if event_date.year < 2025 or (future_only and event_date < today):
                continue
            is_off = bool(item["is_off_day"])
            prefix = "休" if is_off else "班"
            summary = f"{prefix} · {item['name']}" if is_off else f"{prefix} · {item['name']}调休"
            result.append(
                Event(
                    uid=_uid("holiday" if is_off else "workday", item["date"], item["name"]),
                    summary=summary,
                    kind="holiday" if is_off else "workday",
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description=(
                        "国务院办公厅正式放假安排。" if is_off else "国务院办公厅正式调休补班安排。"
                    ),
                    url=source_url,
                    categories=("中国大陆", "法定节假日" if is_off else "调休补班"),
                )
            )
    return result


def solar_term_events(root: Path) -> list[Event]:
    result: list[Event] = []
    for path in sorted((root / "data" / "solar-terms").glob("*.json")):
        payload = _load_json(path)
        for item in payload["terms"]:
            start = datetime.fromisoformat(item["datetime"])
            if start.year < 2025:
                continue
            result.append(
                Event(
                    uid=_uid("solar-term", start.strftime("%Y%m%dT%H%M"), item["name"]),
                    summary=f"节气 · {item['name']} {start:%H:%M}",
                    kind="solar_term",
                    start=start,
                    end=start + timedelta(minutes=1),
                    description=(
                        "二十四节气交节瞬间，按北京时间精确到分钟。"
                        "节气定义遵循太阳视黄经每运行15°的交节口径。"
                        "机器可读时刻来自香港天文台官方天文资料。"
                    ),
                    url=payload["source"],
                    categories=("二十四节气",),
                )
            )
    return result


def traditional_events(root: Path) -> list[Event]:
    result: list[Event] = []
    lunar_by_date: dict[date, dict] = {}
    source_by_year: dict[int, str] = {}
    for path in sorted((root / "data" / "lunar").glob("*.json")):
        payload = _load_json(path)
        source_by_year[int(payload["year"])] = payload["source"]
        for row in payload["days"]:
            lunar_by_date[date.fromisoformat(row["date"])] = row

    for event_date, row in sorted(lunar_by_date.items()):
        if event_date.year < 2025 or row["leap_month"]:
            continue
        name = TRADITIONAL_FESTIVALS.get((row["lunar_month"], row["lunar_day"]))
        if name:
            result.append(
                Event(
                    uid=_uid("traditional", event_date.isoformat(), name),
                    summary=f"传统 · {name}",
                    kind="traditional",
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description="按中国农历日期标注。",
                    url=source_by_year[event_date.year],
                    categories=("传统节日",),
                )
            )

        next_row = lunar_by_date.get(event_date + timedelta(days=1))
        if next_row and next_row["lunar_month"] == 1 and next_row["lunar_day"] == 1:
            result.append(
                Event(
                    uid=_uid("traditional", event_date.isoformat(), "除夕"),
                    summary="传统 · 除夕",
                    kind="traditional",
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description="农历全年最后一天。",
                    url=source_by_year[event_date.year],
                    categories=("传统节日",),
                )
            )
    return result


def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date:
    weeks = calendar.monthcalendar(year, month)
    candidates = [week[weekday] for week in weeks if week[weekday]]
    day = candidates[ordinal - 1] if ordinal > 0 else candidates[ordinal]
    return date(year, month, day)


def observance_events(root: Path) -> list[Event]:
    config = _load_json(root / "config" / "observances.json")
    lunar_years = sorted(int(path.stem) for path in (root / "data" / "lunar").glob("*.json"))
    if not lunar_years:
        return []
    result: list[Event] = []
    for year in range(max(2025, min(lunar_years)), max(lunar_years) + 1):
        for item in config["fixed"]:
            event_date = date(year, item["month"], item["day"])
            result.append(_observance_event(event_date, item))
        for item in config["relative"]:
            event_date = _nth_weekday(
                year, item["month"], item["weekday"], item["ordinal"]
            )
            result.append(_observance_event(event_date, item))
    return result


def _observance_event(event_date: date, item: dict) -> Event:
    group = item["group"]
    return Event(
        uid=_uid("observance", event_date.isoformat(), item["name"]),
        summary=f"纪念 · {item['name']}",
        kind="observance",
        start=event_date,
        end=event_date + timedelta(days=1),
        description=item.get("description", ""),
        url=item.get("url", ""),
        categories=(group,),
    )


def collect_events(root: Path, today: date, future_holidays_only: bool) -> dict[str, list[Event]]:
    groups = {
        "holidays": holiday_events(root, today, future_holidays_only),
        "solar-terms": solar_term_events(root),
        "observances": traditional_events(root) + observance_events(root),
    }
    groups["calendar"] = sorted(
        (event for events in groups.values() for event in events),
        key=lambda event: (event.start.isoformat(), event.summary),
    )
    return groups
