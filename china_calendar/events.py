from __future__ import annotations

import calendar
import json
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
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

SEASONAL_SOURCE = "https://paper.people.com.cn/rmrb/pc/content/202506/02/content_30076651.html"
SHUJIU_SOURCE = "https://www.xiongan.gov.cn/2019-12/20/c_1210404541.htm"


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


def _solar_terms_by_year(root: Path) -> dict[int, dict[str, datetime]]:
    result: dict[int, dict[str, datetime]] = {}
    for path in sorted((root / "data" / "solar-terms").glob("*.json")):
        payload = _load_json(path)
        result[int(payload["year"])] = {
            item["name"]: datetime.fromisoformat(item["datetime"])
            for item in payload["terms"]
        }
    return result


def _is_geng_day(day: date) -> bool:
    """Return whether a Gregorian date is a 庚 day in the sexagenary cycle."""
    julian_day_number = day.toordinal() + 1_721_425
    return (julian_day_number + 9) % 10 == 6


def _geng_days_on_or_after(start: date, count: int) -> list[date]:
    result: list[date] = []
    candidate = start
    while len(result) < count:
        if _is_geng_day(candidate):
            result.append(candidate)
        candidate += timedelta(days=1)
    return result


def _seasonal_event(
    event_date: date,
    name: str,
    description: str,
    url: str,
    *categories: str,
) -> Event:
    return Event(
        uid=_uid("seasonal", event_date.isoformat(), name),
        summary=f"时令 · {name}",
        kind="seasonal",
        start=event_date,
        end=event_date + timedelta(days=1),
        description=description,
        url=url,
        categories=("传统时令", *categories),
    )


def dog_days_events(root: Path) -> list[Event]:
    result: list[Event] = []
    for year, terms in _solar_terms_by_year(root).items():
        if year < 2025 or "夏至" not in terms or "立秋" not in terms:
            continue
        summer_geng = _geng_days_on_or_after(terms["夏至"].date(), 4)
        autumn_geng = _geng_days_on_or_after(terms["立秋"].date(), 2)
        initial, middle = summer_geng[2], summer_geng[3]
        final, after = autumn_geng[0], autumn_geng[1]
        periods = (
            (initial, "初伏", initial, middle),
            (middle, "中伏", middle, final),
            (final, "末伏", final, after),
        )
        for event_date, name, start, end in periods:
            days = (end - start).days
            result.append(
                _seasonal_event(
                    event_date,
                    name,
                    f"{name}从{start:%Y年%m月%d日}起，共{days}天；"
                    "按干支纪日推算，初伏为夏至后第三个庚日，"
                    "中伏为第四个庚日，"
                    "末伏为立秋后第一个庚日。",
                    SEASONAL_SOURCE,
                    "三伏",
                )
            )
        result.append(
            _seasonal_event(
                after,
                "出伏",
                f"末伏于{after - timedelta(days=1):%Y年%m月%d日}结束，今日出伏。",
                SEASONAL_SOURCE,
                "三伏",
            )
        )
    return result


def nine_nines_events(root: Path) -> list[Event]:
    result: list[Event] = []
    labels = "一二三四五六七八九"
    for terms in _solar_terms_by_year(root).values():
        if "冬至" not in terms:
            continue
        winter_solstice = terms["冬至"].date()
        for index, label in enumerate(labels):
            event_date = winter_solstice + timedelta(days=index * 9)
            if event_date.year < 2025:
                continue
            period_end = event_date + timedelta(days=8)
            result.append(
                _seasonal_event(
                    event_date,
                    f"{label}九",
                    f"{label}九从{event_date:%Y年%m月%d日}至{period_end:%Y年%m月%d日}。"
                    "数九从冬至当天起，每九天为一九。",
                    SHUJIU_SOURCE,
                    "数九",
                )
            )
        out_date = winter_solstice + timedelta(days=81)
        if out_date.year >= 2025:
            result.append(
                _seasonal_event(
                    out_date,
                    "出九",
                    "九九八十一天结束，今日出九。",
                    SHUJIU_SOURCE,
                    "数九",
                )
            )
    return result


def shanghai_meiyu_events(root: Path) -> list[Event]:
    config = _load_json(root / "config" / "shanghai-meiyu.json")
    result: list[Event] = []
    for item in config["years"]:
        if item.get("status") != "published":
            continue
        start = date.fromisoformat(item["start"])
        end = date.fromisoformat(item["end"])
        expected_year = int(item["year"])
        if start.year != expected_year or end.year != expected_year or end <= start:
            raise ValueError(f"Invalid Shanghai meiyu period for {expected_year}")
        for key in ("start_source", "end_source"):
            parsed = urlparse(item[key])
            if parsed.scheme != "https" or parsed.hostname != "www.shanghai.gov.cn":
                raise ValueError(f"Non-official Shanghai meiyu source: {item[key]}")
        result.extend(
            [
                _seasonal_event(
                    start,
                    "上海入梅",
                    "上海气象部门正式公布今日入梅；"
                    f"本年梅雨期至{end:%m月%d日}。"
                    "日期仅在官方公布后收录，不按常年平均日期预测。",
                    item["start_source"],
                    "上海梅雨",
                ),
                _seasonal_event(
                    end,
                    "上海出梅",
                    "上海气象部门正式公布今日出梅；"
                    f"本年梅雨期始于{start:%m月%d日}。"
                    "日期仅在官方公布后收录，不按常年平均日期预测。",
                    item["end_source"],
                    "上海梅雨",
                ),
            ]
        )
    return result


def _health_event(event_date: date, name: str, description: str, url: str) -> Event:
    return Event(
        uid=_uid("health", event_date.isoformat(), name),
        summary=f"健康提醒 · {name}",
        kind="health",
        start=event_date,
        end=event_date + timedelta(days=1),
        description=(
            f"{description} 节气和时令仅作季节参考，"
            "请以当地天气预报、气象预警及"
            "自身情况调整安排；出现明显不适请及时就医。"
        ),
        url=url,
        categories=("季节健康提醒", "天气健康"),
    )


def health_events(root: Path) -> list[Event]:
    config = _load_json(root / "config" / "seasonal-health.json")
    reminders = {item["term"]: item for item in config["solar_terms"]}
    result: list[Event] = []
    terms_by_year = _solar_terms_by_year(root)
    for year, terms in terms_by_year.items():
        if year < 2025:
            continue
        for term, start in terms.items():
            item = reminders[term]
            result.append(
                _health_event(
                    start.date(),
                    f"{term}·{item['title']}",
                    item["description"],
                    item["url"],
                )
            )

    dog_days = dog_days_events(root)
    for event in dog_days:
        if event.summary == "时令 · 初伏":
            result.append(
                _health_event(
                    event.start,  # type: ignore[arg-type]
                    "入伏防暑",
                    "高温高湿时减少午后长时间户外活动，主动少量多次补水，"
                    "关注头晕、恶心、乏力等中暑信号。",
                    config["sources"]["heat"],
                )
            )

    meiyu = shanghai_meiyu_events(root)
    for event in meiyu:
        if event.summary == "时令 · 上海入梅":
            result.append(
                _health_event(
                    event.start,  # type: ignore[arg-type]
                    "上海梅雨防潮防霉",
                    "及时通风或除湿，湿衣尽快洗净晾干；"
                    "食品密封、按需冷藏，"
                    "发现霉变食品直接丢弃。",
                    config["sources"]["meiyu"],
                )
            )
        elif event.summary == "时令 · 上海出梅":
            result.append(
                _health_event(
                    event.start,  # type: ignore[arg-type]
                    "上海出梅防高温",
                    "出梅后常转入晴热天气，提前关注高温预警，"
                    "安排好遮阳、补水和"
                    "室内降温。",
                    config["sources"]["heat"],
                )
            )
    return result


def seasonal_events(root: Path) -> list[Event]:
    return sorted(
        dog_days_events(root)
        + nine_nines_events(root)
        + shanghai_meiyu_events(root)
        + health_events(root),
        key=lambda event: (event.start.isoformat(), event.summary),
    )


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
    solar_terms: list[Event],
    traditional: list[Event],
    observances: list[Event],
    seasonal: list[Event],
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
    for event in seasonal:
        result.append(replace(event, uid=f"supplement-{event.uid}"))
    return sorted(result, key=lambda event: (event.start.isoformat(), event.summary))


def collect_events(root: Path, today: date, future_holidays_only: bool) -> dict[str, list[Event]]:
    solar_terms = solar_term_events(root)
    traditional = traditional_events(root)
    observances = observance_events(root)
    seasonal = seasonal_events(root)
    groups = {
        "holidays": holiday_events(root, today, future_holidays_only),
        "solar-terms": solar_terms,
        "observances": traditional + observances,
        "seasonal": seasonal,
    }
    groups["calendar"] = sorted(
        (event for events in groups.values() for event in events),
        key=lambda event: (event.start.isoformat(), event.summary),
    )
    groups["supplement"] = supplement_events(
        solar_terms, traditional, observances, seasonal
    )
    return groups
