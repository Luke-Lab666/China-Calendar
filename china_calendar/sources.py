from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


HOLIDAY_URL = "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json"
HKO_SOLAR_URL = (
    "https://www.hko.gov.hk/tc/gts/astronomy/data/files/24SolarTerms_{year}.xml"
)
HKO_LUNAR_URL = (
    "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt"
)

SOLAR_TERM_NAMES = (
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分",
    "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
    "小暑", "大暑", "立秋", "处暑", "白露", "秋分",
    "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
)

TRADITIONAL_TO_SIMPLIFIED = str.maketrans(
    {
        "曆": "历", "農": "农", "節": "节", "氣": "气", "驚": "惊",
        "蟄": "蛰", "穀": "谷", "滿": "满", "種": "种", "處": "处",
        "馬": "马", "閏": "闰", "臘": "腊",
    }
)

MONTHS = {
    "正月": 1,
    "一月": 1,
    "二月": 2,
    "三月": 3,
    "四月": 4,
    "五月": 5,
    "六月": 6,
    "七月": 7,
    "八月": 8,
    "九月": 9,
    "十月": 10,
    "十一月": 11,
    "十二月": 12,
}

DAY_NUMBERS = {
    "初一": 1, "初二": 2, "初三": 3, "初四": 4, "初五": 5,
    "初六": 6, "初七": 7, "初八": 8, "初九": 9, "初十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15,
    "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
    "廿一": 21, "廿二": 22, "廿三": 23, "廿四": 24, "廿五": 25,
    "廿六": 26, "廿七": 27, "廿八": 28, "廿九": 29, "三十": 30,
}


class SourceError(RuntimeError):
    pass


@dataclass(slots=True)
class FetchResult:
    body: bytes
    url: str


class HttpClient:
    def __init__(self, timeout: int = 30, max_bytes: int = 2_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def get(self, url: str) -> FetchResult:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise SourceError(f"Refusing non-HTTPS source: {url}")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Luke-Lab666/China-Calendar (+GitHub Actions)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read(self.max_bytes + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SourceError(f"Unable to fetch {url}: {exc}") from exc
        if len(body) > self.max_bytes:
            raise SourceError(f"Source exceeds {self.max_bytes} bytes: {url}")
        return FetchResult(body=body, url=url)

    def get_optional(self, url: str) -> FetchResult | None:
        try:
            return self.get(url)
        except SourceError as exc:
            if isinstance(exc.__cause__, urllib.error.HTTPError) and exc.__cause__.code == 404:
                return None
            raise


def parse_holidays(raw: bytes, expected_year: int) -> dict:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"Invalid holiday JSON for {expected_year}") from exc
    if payload.get("year") != expected_year:
        raise SourceError(f"Holiday year mismatch: expected {expected_year}")
    papers = payload.get("papers")
    days = payload.get("days")
    if not isinstance(papers, list) or not isinstance(days, list):
        raise SourceError(f"Invalid holiday schema for {expected_year}")
    for paper in papers:
        parsed = urlparse(paper)
        if parsed.scheme != "https" or parsed.hostname not in {"www.gov.cn", "gov.cn"}:
            raise SourceError(f"Non-official holiday paper URL: {paper}")
    if days and not papers:
        raise SourceError(f"Holiday data for {expected_year} has no official paper")
    normalized_days: list[dict] = []
    for item in days:
        if set(item) < {"name", "date", "isOffDay"}:
            raise SourceError(f"Invalid holiday day for {expected_year}: {item!r}")
        parsed_date = date.fromisoformat(item["date"])
        if parsed_date.year not in {expected_year - 1, expected_year, expected_year + 1}:
            raise SourceError(f"Holiday date too far from notice year: {parsed_date}")
        if not isinstance(item["isOffDay"], bool):
            raise SourceError(f"Invalid isOffDay value: {item!r}")
        normalized_days.append(
            {
                "date": parsed_date.isoformat(),
                "name": str(item["name"]).strip(),
                "is_off_day": item["isOffDay"],
            }
        )
    return {
        "year": expected_year,
        "papers": papers,
        "days": sorted(normalized_days, key=lambda item: item["date"]),
    }


def parse_solar_terms(raw: bytes, year: int) -> dict:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SourceError(f"Invalid HKO solar-term XML for {year}") from exc
    rows = root.findall("Data")
    if len(rows) != 24:
        raise SourceError(f"Expected 24 solar terms for {year}, got {len(rows)}")
    terms: list[dict] = []
    for name, row in zip(SOLAR_TERM_NAMES, rows, strict=True):
        month = int(row.findtext("M", ""))
        day = int(row.findtext("D", ""))
        time_text = row.findtext("hm", "")
        if not re.fullmatch(r"[0-2]\d:[0-5]\d", time_text):
            raise SourceError(f"Invalid HKO solar-term time: {time_text!r}")
        stamp = datetime.fromisoformat(f"{year:04d}-{month:02d}-{day:02d}T{time_text}:00+08:00")
        terms.append({"name": name, "datetime": stamp.isoformat()})
    return {
        "year": year,
        "source": HKO_SOLAR_URL.format(year=year),
        "timezone": "Asia/Shanghai",
        "precision": "minute",
        "terms": terms,
    }


_LUNAR_LINE = re.compile(
    r"^(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日\s+"
    r"(?P<lunar>\S+)\s+星期\S+(?:\s+(?P<term>\S+))?$"
)


def _previous_lunar_month(month: int) -> int:
    return 12 if month == 1 else month - 1


def parse_lunar_calendar(raw: bytes, year: int) -> dict:
    text = raw.decode("utf-8-sig").translate(TRADITIONAL_TO_SIMPLIFIED)
    parsed_rows: list[dict] = []
    first_month_marker: tuple[int, bool] | None = None
    current_month: int | None = None
    current_leap = False

    for line in text.splitlines():
        match = _LUNAR_LINE.match(line.strip())
        if not match:
            continue
        lunar_text = match.group("lunar")
        marker = lunar_text.removeprefix("闰")
        if marker in MONTHS:
            current_month = MONTHS[marker]
            current_leap = lunar_text.startswith("闰")
            lunar_day = 1
            if first_month_marker is None:
                first_month_marker = (current_month, current_leap)
        else:
            if lunar_text not in DAY_NUMBERS:
                raise SourceError(f"Unknown lunar day {lunar_text!r} for {year}")
            lunar_day = DAY_NUMBERS[lunar_text]
        parsed_rows.append(
            {
                "date": f"{int(match.group('year')):04d}-{int(match.group('month')):02d}-{int(match.group('day')):02d}",
                "lunar_month": current_month,
                "lunar_day": lunar_day,
                "leap_month": current_leap if current_month is not None else None,
                "solar_term": (match.group("term") or "").translate(TRADITIONAL_TO_SIMPLIFIED),
            }
        )

    expected_count = 366 if _is_leap_year(year) else 365
    if len(parsed_rows) != expected_count or first_month_marker is None:
        raise SourceError(
            f"Expected {expected_count} HKO lunar rows for {year}, got {len(parsed_rows)}"
        )

    first_month, _ = first_month_marker
    initial_month = _previous_lunar_month(first_month)
    for row in parsed_rows:
        if row["lunar_month"] is not None:
            break
        row["lunar_month"] = initial_month
        row["leap_month"] = False

    # The first pass cannot propagate a newly encountered month to rows already appended.
    active_month = initial_month
    active_leap = False
    for row in parsed_rows:
        if row["lunar_day"] == 1:
            active_month = int(row["lunar_month"])
            active_leap = bool(row["leap_month"])
        else:
            row["lunar_month"] = active_month
            row["leap_month"] = active_leap

    return {
        "year": year,
        "source": HKO_LUNAR_URL.format(year=year),
        "days": parsed_rows,
    }


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def write_json_if_changed(path: Path, payload: dict) -> bool:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def update_source_state(root: Path, changed: bool) -> str:
    state_path = root / "data" / "source-state.json"
    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    source_files = sorted(
        path for path in (root / "data").rglob("*.json") if path != state_path
    )
    digest = hashlib.sha256()
    for path in source_files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    source_digest = digest.hexdigest()
    if not changed and previous.get("source_digest") == source_digest:
        return str(previous["generated_at"])
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_json_if_changed(
        state_path,
        {"generated_at": generated_at, "source_digest": source_digest},
    )
    return generated_at


def fetch_all(root: Path, today: date, client: HttpClient | None = None) -> str:
    client = client or HttpClient()
    current_year = today.year
    years = range(max(2025, current_year - 1), current_year + 3)
    # Keep the preceding winter solstice so that the early-January "数九"
    # markers are complete for the first published calendar year.
    solar_years = range(max(2024, current_year - 2), current_year + 3)
    changed = False

    for year in years:
        holiday_result = client.get_optional(HOLIDAY_URL.format(year=year))
        if holiday_result is None:
            if year <= current_year:
                raise SourceError(f"Missing current or historical holiday data for {year}")
            holiday_payload = {"year": year, "papers": [], "days": []}
        else:
            holiday_payload = parse_holidays(holiday_result.body, year)
        changed |= write_json_if_changed(
            root / "data" / "holidays" / f"{year}.json",
            holiday_payload,
        )

        lunar_raw = client.get(HKO_LUNAR_URL.format(year=year)).body
        changed |= write_json_if_changed(
            root / "data" / "lunar" / f"{year}.json",
            parse_lunar_calendar(lunar_raw, year),
        )

    for year in solar_years:
        solar_raw = client.get(HKO_SOLAR_URL.format(year=year)).body
        changed |= write_json_if_changed(
            root / "data" / "solar-terms" / f"{year}.json",
            parse_solar_terms(solar_raw, year),
        )

    return update_source_state(root, changed)
