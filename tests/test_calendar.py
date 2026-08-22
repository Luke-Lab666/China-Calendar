from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from china_calendar.events import collect_events
from china_calendar.ical import render_calendar
from china_calendar.sources import SourceError, parse_holidays, parse_solar_terms


ROOT = Path(__file__).resolve().parents[1]


class SourceParserTests(unittest.TestCase):
    def test_holidays_require_official_gov_cn_paper(self) -> None:
        raw = json.dumps(
            {
                "year": 2027,
                "papers": ["https://example.com/fake"],
                "days": [{"name": "元旦", "date": "2027-01-01", "isOffDay": True}],
            }
        ).encode()
        with self.assertRaises(SourceError):
            parse_holidays(raw, 2027)

    def test_empty_unannounced_year_is_allowed_but_has_no_days(self) -> None:
        payload = parse_holidays(b'{"year":2027,"papers":[],"days":[]}', 2027)
        self.assertEqual(payload["days"], [])

    def test_solar_terms_require_exactly_24_rows(self) -> None:
        with self.assertRaises(SourceError):
            parse_solar_terms(b"<SolarTerms_2026 />", 2026)


@unittest.skipUnless((ROOT / "data" / "source-state.json").exists(), "source data not generated")
class GeneratedCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = collect_events(ROOT, date(2026, 8, 22), future_holidays_only=False)
        cls.generated_at = json.loads(
            (ROOT / "data" / "source-state.json").read_text(encoding="utf-8")
        )["generated_at"]

    def test_known_2026_solar_term_minute(self) -> None:
        event = next(
            event
            for event in self.groups["solar-terms"]
            if event.summary == "立春" and event.start.year == 2026
        )
        self.assertIsInstance(event.start, datetime)
        self.assertEqual(event.start.isoformat(), "2026-02-04T04:02:00+08:00")

    def test_known_2026_makeup_workday(self) -> None:
        event = next(
            event
            for event in self.groups["holidays"]
            if event.start == date(2026, 2, 14)
        )
        self.assertEqual(event.kind, "workday")
        self.assertEqual(event.summary, "春节（班）")
        self.assertEqual(event.apple_special_day, "ALTERNATE-WORKDAY")

    def test_2026_national_day_is_one_multiday_holiday(self) -> None:
        events = [
            event
            for event in self.groups["holidays"]
            if event.summary == "国庆节（休）" and event.start.year == 2026
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].start, date(2026, 10, 1))
        self.assertEqual(events[0].end, date(2026, 10, 8))
        self.assertEqual(events[0].apple_special_day, "WORK-HOLIDAY")

    def test_supplement_avoids_official_apple_holiday_duplicates(self) -> None:
        supplement = self.groups["supplement"]
        self.assertTrue(all(event.kind not in {"holiday", "workday"} for event in supplement))
        summaries = {event.summary for event in supplement}
        self.assertNotIn("国际妇女节", summaries)
        self.assertNotIn("春节", summaries)
        self.assertIn("南京大屠杀死难者国家公祭日", summaries)
        self.assertIn("腊八节", summaries)

    def test_supplement_keeps_minute_accurate_solar_term(self) -> None:
        event = next(
            event
            for event in self.groups["supplement"]
            if event.summary == "寒露 · 14:29交节" and event.start.year == 2026
        )
        self.assertEqual(event.start.isoformat(), "2026-10-08T14:29:00+08:00")

    def test_unannounced_year_does_not_invent_holidays(self) -> None:
        holidays = [event for event in self.groups["holidays"] if event.start.year == 2027]
        self.assertEqual(holidays, [])

    def test_no_event_before_2025(self) -> None:
        self.assertTrue(all(event.start.year >= 2025 for event in self.groups["calendar"]))

    def test_ics_is_crlf_folded_and_has_unique_uids(self) -> None:
        content = render_calendar("calendar", self.groups["calendar"], self.generated_at)
        self.assertNotIn(b"\n", content.replace(b"\r\n", b""))
        for line in content.split(b"\r\n"):
            self.assertLessEqual(len(line), 75)
        text = content.decode("utf-8")
        uids = re.findall(r"^UID:(.+)$", text, flags=re.MULTILINE)
        self.assertEqual(len(uids), len(set(uids)))
        self.assertNotIn("BEGIN:VALARM", text)
        self.assertIn("X-APPLE-LANGUAGE:zh", text)
        self.assertIn("X-APPLE-REGION:CN", text)
        self.assertIn("X-APPLE-CALENDAR-COLOR:#FF9500", text)
        self.assertIn("X-APPLE-SPECIAL-DAY:WORK-HOLIDAY", text)
        self.assertIn("X-APPLE-SPECIAL-DAY:ALTERNATE-WORKDAY", text)

    def test_supplement_calendar_renders_without_special_day_markers(self) -> None:
        content = render_calendar(
            "supplement", self.groups["supplement"], self.generated_at
        ).decode("utf-8")
        self.assertIn("X-WR-CALNAME:中国日历补充・精确交节与纪念日", content)
        self.assertNotIn("X-APPLE-SPECIAL-DAY:", content)

    def test_future_only_filters_only_official_arrangements(self) -> None:
        groups = collect_events(ROOT, date(2026, 8, 22), future_holidays_only=True)
        self.assertTrue(all(event.start >= date(2026, 8, 22) for event in groups["holidays"]))
        self.assertTrue(
            any(event.start.date() < date(2026, 8, 22) for event in groups["solar-terms"])
        )


if __name__ == "__main__":
    unittest.main()
