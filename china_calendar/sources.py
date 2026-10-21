from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .storage import write_if_changed


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
    def __init__(self, timeout: int = 20, max_bytes: int = 2_000_000, retries: int = 2) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.retries = retries

    def get(self, url: str) -> FetchResult:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise SourceError(f"Refusing non-HTTPS source: {url}")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Luke-Lab666/China-Calendar (+GitHub Actions)"},
        )
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    if urlparse(response.geturl()).scheme != "https":
                        raise SourceError(f"Refusing non-HTTPS redirect: {url}")
                    body = response.read(self.max_bytes + 1)
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in {
                    408, 429, 500, 502, 503, 504
                }
                if not retryable or attempt == self.retries:
                    raise SourceError(f"Unable to fetch {url}: {exc}") from exc
                time.sleep(2 ** attempt)
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
    if not isinstance(payload, dict) or payload.get("year") != expected_year:
        raise SourceError(f"Holiday year mismatch: expected {expected_year}")
    papers = payload.get("papers")
    days = payload.get("days")
    if not isinstance(papers, list) or not isinstance(days, list):
        raise SourceError(f"Invalid holiday schema for {expected_year}")
    for paper in papers:
        if not isinstance(paper, str):
            raise SourceError(f"Invalid holiday paper for {expected_year}")
        parsed = urlparse(paper)
        if parsed.scheme != "https" or parsed.hostname not in {"www.gov.cn", "gov.cn"}:
            raise SourceError(f"Non-official holiday paper URL: {paper}")
    if days and not papers:
        raise SourceError(f"Holiday data for {expected_year} has no official paper")
    normalized_days: list[dict] = []
    seen: set[str] = set()
    for item in days:
        if not isinstance(item, dict) or not {"name", "date", "isOffDay"} <= item.keys():
            raise SourceError(f"Invalid holiday day for {expected_year}: {item!r}")
        try:
            parsed_date = date.fromisoformat(item["date"])
        except (TypeError, ValueError) as exc:
            raise SourceError(f"Invalid holiday date: {item['date']!r}") from exc
        if parsed_date.isoformat() in seen:
            raise SourceError(f"Duplicate holiday date: {parsed_date}")
        seen.add(parsed_date.isoformat())
        if parsed_date.year not in {expected_year - 1, expected_year, expected_year + 1}:
            raise SourceError(f"Holiday date too far from notice year: {parsed_date}")
        if not isinstance(item["isOffDay"], bool):
            raise SourceError(f"Invalid isOffDay value: {item!r}")
        if not isinstance(item["name"], str) or not item["name"].strip():
            raise SourceError(f"Invalid holiday name: {item!r}")
        normalized_days.append(
            {
                "date": parsed_date.isoformat(),
                "name": item["name"].strip(),
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
    try:
        for index, (name, row) in enumerate(zip(SOLAR_TERM_NAMES, rows, strict=True)):
            month = int(row.findtext("M", ""))
            day = int(row.findtext("D", ""))
            time_text = row.findtext("hm", "")
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_text):
                raise ValueError(f"Invalid time: {time_text!r}")
            if month != index // 2 + 1:
                raise ValueError(f"Unexpected month for {name}: {month}")
            stamp = datetime.fromisoformat(f"{year:04d}-{month:02d}-{day:02d}T{time_text}:00+08:00")
            if terms and stamp.isoformat() <= terms[-1]["datetime"]:
                raise ValueError("Solar terms must be chronological")
            terms.append({"name": name, "datetime": stamp.isoformat()})
    except ValueError as exc:
        raise SourceError(f"Invalid HKO solar-term data for {year}: {exc}") from exc
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
    try:
        text = raw.decode("utf-8-sig").translate(TRADITIONAL_TO_SIMPLIFIED)
    except UnicodeDecodeError as exc:
        raise SourceError(f"Invalid HKO lunar encoding for {year}") from exc
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

    for index, row in enumerate(parsed_rows):
        expected_date = (date(year, 1, 1) + timedelta(days=index)).isoformat()
        if row["date"] != expected_date:
            raise SourceError(f"Missing, duplicate or out-of-order lunar date: expected {expected_date}")

    first_month, first_is_leap = first_month_marker
    initial_month = first_month if first_is_leap else _previous_lunar_month(first_month)
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
    return write_if_changed(path, content.encode("utf-8"))


def update_source_state(
    root: Path, build_options: dict | None = None,
    *, state_path: Path | None = None, persist: bool = True,
) -> str:
    canonical_state = root / "data" / "source-state.json"
    state_path = state_path or canonical_state
    previous = {}
    if state_path.exists():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    source_files = sorted([
        *(path for path in (root / "data").rglob("*.json") if path not in {state_path, canonical_state}),
        *(root / "config").glob("*.json"),
        *(root / "china_calendar").glob("*.py"),
    ])
    digest = hashlib.sha256()
    digest.update(json.dumps(build_options or {}, sort_keys=True).encode())
    for path in source_files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    source_digest = digest.hexdigest()
    if previous.get("source_digest") == source_digest:
        return str(previous["generated_at"])
    if not persist:
        raise SourceError("生成状态已过期，请运行 --offline 重新生成订阅")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_json_if_changed(
        state_path,
        {"generated_at": generated_at, "source_digest": source_digest, "build_options": build_options or {}},
    )
    return generated_at


def fetch_all(root: Path, today: date, client: HttpClient | None = None) -> None:
    client = client or HttpClient()
    current_year = today.year
    years = range(max(2025, current_year - 1), current_year + 3)
    # Keep the preceding winter solstice so that the early-January "数九"
    # markers are complete for the first published calendar year.
    solar_years = range(max(2024, current_year - 2), current_year + 3)
    # Stage every response in memory. A broken final source must not leave a
    # mix of old and new source files behind.
    pending: dict[Path, dict | None] = {}

    for year in years:
        holiday_result = client.get_optional(HOLIDAY_URL.format(year=year))
        if holiday_result is None:
            if year <= current_year:
                raise SourceError(f"Missing current or historical holiday data for {year}")
            holiday_payload = {"year": year, "papers": [], "days": []}
        else:
            holiday_payload = parse_holidays(holiday_result.body, year)
        holiday_path = root / "data" / "holidays" / f"{year}.json"
        if not holiday_payload["days"]:
            if year <= current_year:
                raise SourceError(f"Empty current or historical holiday data for {year}")
            if holiday_path.exists() and json.loads(holiday_path.read_text(encoding="utf-8"))["days"]:
                raise SourceError(f"Refusing to erase published holiday data for {year}")
        pending[holiday_path] = holiday_payload if holiday_payload["days"] else None

        lunar_raw = client.get(HKO_LUNAR_URL.format(year=year)).body
        pending[root / "data" / "lunar" / f"{year}.json"] = parse_lunar_calendar(lunar_raw, year)

    for year in solar_years:
        solar_raw = client.get(HKO_SOLAR_URL.format(year=year)).body
        pending[root / "data" / "solar-terms" / f"{year}.json"] = parse_solar_terms(solar_raw, year)

    for path, payload in pending.items():
        if payload is None:
            path.unlink(missing_ok=True)
        else:
            write_json_if_changed(path, payload)
