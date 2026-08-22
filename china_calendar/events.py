from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import replace
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

# These are already included in Apple's official "中国大陆节假日" calendar.
# The supplement feed keeps only material Apple does not provide, apart from
# minute-accurate solar-term transition events which intentionally add detail.
APPLE_TRADITIONAL_NAMES = {"春节", "元宵节", "端午节", "七夕", "中秋节", "重阳节", "除夕"}
APPLE_OBSERVANCE_NAMES = {
    "国际妇女节",
    "五四青年节",
    "国际儿童节",
    "中国共产党成立纪念日",
    "中国人民解放军建军节",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _uid(kind: str, day_or_stamp: str, name: str) -> str:
    safe_name = "".join(ch for ch in name if ch.isascii() and ch.isalnum()) or name.encode().hex()
    return f"{kind}-{day_or_stamp}-{safe_name}@china-calendar.luke-lab666"


def _apple_id(kind: str, name: str) -> str:
    """Stable identifier used by Apple Calendar to relate recurring concepts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"china-calendar:{kind}:{name}"))


def _holiday_name(name: str) -> str:
    # Official source combines overlapping arrangements (for example
    # "国庆节、中秋节").  The traditional festival remains a separate event.
    if "国庆节" in name:
        return "国庆节"
    return name.split("、", 1)[0]


def holiday_events(root: Path, today: date, future_only: bool) -> list[Event]:
    result: list[Event] = []
    for path in sorted((root / "data" / "holidays").glob("*.json")):
        payload = _load_json(path)
        if not payload["papers"]:
            continue
        source_url = payload["papers"][0]
        days = []
        for item in payload["days"]:
            event_date = date.fromisoformat(item["date"])
            if event_date.year >= 2025 and not (future_only and event_date < today):
                days.append((event_date, bool(item["is_off_day"]), _holiday_name(item["name"])))

        off_days = sorted((day, name) for day, is_off, name in days if is_off)
        index = 0
        while index < len(off_days):
            start, name = off_days[index]
            end = start + timedelta(days=1)
            index += 1
            while index < len(off_days) and off_days[index] == (end, name):
                end += timedelta(days=1)
                index += 1
            result.append(
                Event(
                    uid=_uid("holiday", f"{start.isoformat()}-{end.isoformat()}", name),
                    summary=f"{name}（休）",
                    kind="holiday",
                    start=start,
                    end=end,
                    description="国务院办公厅正式放假安排。",
                    url=source_url,
                    categories=("中国大陆", "法定节假日"),
                    apple_special_day="WORK-HOLIDAY",
                    apple_universal_id=_apple_id("holiday", name),
                )
            )

        for event_date, is_off, name in days:
            if is_off:
                continue
            result.append(
                Event(
                    uid=_uid("workday", event_date.isoformat(), name),
                    summary=f"{name}（班）",
                    kind="workday",
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description="国务院办公厅正式调休补班安排。",
                    url=source_url,
                    categories=("中国大陆", "调休补班"),
                    apple_special_day="ALTERNATE-WORKDAY",
                    apple_universal_id=_apple_id("holiday", name),
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
                    summary=item["name"],
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
                    apple_universal_id=_apple_id("solar-term", item["name"]),
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


def supplement_events(
    solar_terms: list[Event], traditional: list[Event], observances: list[Event]
) -> list[Event]:
    """Events intended to accompany Apple's official mainland holiday calendar."""
    result: list[Event] = []
    for event in solar_terms:
        assert isinstance(event.start, datetime)
        result.append(
            replace(
                event,
                uid=f"supplement-{event.uid}",
                summary=f"{event.summary} · {event.start:%H:%M}交节",
            )
        )
    for event in traditional:
        name = event.summary.removeprefix("传统 · ")
        if name not in APPLE_TRADITIONAL_NAMES:
            result.append(
                replace(event, uid=f"supplement-{event.uid}", summary=name)
            )
    for event in observances:
        name = event.summary.removeprefix("纪念 · ")
        if name not in APPLE_OBSERVANCE_NAMES:
            result.append(
                replace(event, uid=f"supplement-{event.uid}", summary=name)
            )
    return sorted(result, key=lambda event: (event.start.isoformat(), event.summary))


def collect_events(root: Path, today: date, future_holidays_only: bool) -> dict[str, list[Event]]:
    solar_terms = solar_term_events(root)
    traditional = traditional_events(root)
    observances = observance_events(root)
    groups = {
        "holidays": holiday_events(root, today, future_holidays_only),
        "solar-terms": solar_terms,
        "observances": traditional + observances,
    }
    groups["calendar"] = sorted(
        (event for events in groups.values() for event in events),
        key=lambda event: (event.start.isoformat(), event.summary),
    )
    groups["supplement"] = supplement_events(solar_terms, traditional, observances)
    return groups
