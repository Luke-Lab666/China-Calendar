from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from china_calendar.cli import main
from china_calendar.events import collect_events, holiday_events, overlaps
from china_calendar.ical import render_calendar, write_calendars
from china_calendar.models import Event
from china_calendar.query import day_record
from china_calendar.sources import (
    DAY_NUMBERS, MONTHS, FetchResult, HttpClient, SourceError, fetch_all,
    parse_holidays, parse_lunar_calendar, parse_solar_terms, update_source_state,
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-10-21T08:00:00+00:00"
PAPER = "https://www.gov.cn/zhengce/test.htm"


def holiday_raw(**changes) -> bytes:
    payload = {
        "year": 2026, "papers": [PAPER],
        "days": [{"name": "元旦", "date": "2026-01-01", "isOffDay": True}],
    }
    payload.update(changes)
    return json.dumps(payload).encode()


def solar_raw(year: int) -> bytes:
    payload = json.loads((ROOT / "data" / "solar-terms" / f"{year}.json").read_text())
    rows = []
    for item in payload["terms"]:
        stamp = datetime.fromisoformat(item["datetime"])
        rows.append(f"<Data><M>{stamp.month}</M><D>{stamp.day}</D><hm>{stamp:%H:%M}</hm></Data>")
    return ("<SolarTerms>" + "".join(rows) + "</SolarTerms>").encode()


def lunar_raw(year: int) -> bytes:
    payload = json.loads((ROOT / "data" / "lunar" / f"{year}.json").read_text())
    months = {number: name for name, number in MONTHS.items()}
    days = {number: name for name, number in DAY_NUMBERS.items()}
    rows = []
    for item in payload["days"]:
        day = date.fromisoformat(item["date"])
        lunar = (("闰" if item["leap_month"] else "") + months[item["lunar_month"]]
                 if item["lunar_day"] == 1 else days[item["lunar_day"]])
        rows.append(f"{day.year}年{day.month}月{day.day}日 {lunar} 星期一 {item['solar_term']}".strip())
    return "\n".join(rows).encode()


class StrictSourceTests(unittest.TestCase):
    def test_bad_holiday_schemas_raise_source_error(self):
        bad = [
            b"[]", b"null", b"{}", holiday_raw(papers=[None]),
            holiday_raw(days=[None]),
            holiday_raw(days=[{"date": "2026-01-01", "extra": 1}]),
            holiday_raw(days=[{"name": "元旦", "date": "bad", "isOffDay": True}]),
            holiday_raw(days=[{"name": "", "date": "2026-01-01", "isOffDay": True}]),
            holiday_raw(days=[{"name": "元旦", "date": "2026-01-01", "isOffDay": 1}]),
        ]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(SourceError):
                parse_holidays(raw, 2026)

    def test_duplicate_holiday_dates_rejected(self):
        days = [{"name": "元旦", "date": "2026-01-01", "isOffDay": True}] * 2
        with self.assertRaisesRegex(SourceError, "Duplicate"):
            parse_holidays(holiday_raw(days=days), 2026)

    def test_solar_terms_roundtrip_cached_dates(self):
        self.assertEqual(len(parse_solar_terms(solar_raw(2026), 2026)["terms"]), 24)

    def test_invalid_solar_hour_and_order_raise_source_error(self):
        raw = solar_raw(2026)
        for invalid in [raw.replace(b"16:23", b"29:23"), raw.replace(b"<M>1</M>", b"<M>2</M>", 1)]:
            with self.subTest(raw=invalid[:80]), self.assertRaises(SourceError):
                parse_solar_terms(invalid, 2026)

    def test_lunar_roundtrip_including_leap_month_and_leap_year(self):
        for year in (2025, 2026, 2027, 2028):
            with self.subTest(year=year):
                expected = json.loads((ROOT / "data" / "lunar" / f"{year}.json").read_text())
                self.assertEqual(parse_lunar_calendar(lunar_raw(year), year)["days"], expected["days"])

    def test_duplicate_lunar_date_cannot_pass_by_row_count(self):
        rows = lunar_raw(2026).splitlines()
        rows[1] = rows[0]
        with self.assertRaisesRegex(SourceError, "lunar date"):
            parse_lunar_calendar(b"\n".join(rows), 2026)

    def test_http_retries_temporary_errors(self):
        response = Mock()
        response.geturl.return_value = "https://example.com/data"
        response.read.return_value = b"ok"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("urllib.request.urlopen", side_effect=[urllib.error.URLError("temporary"), response]) as get:
            with patch("china_calendar.sources.time.sleep"):
                self.assertEqual(HttpClient().get("https://example.com/data").body, b"ok")
        self.assertEqual(get.call_count, 2)

    def test_404_is_optional_and_is_not_retried(self):
        error = urllib.error.HTTPError("https://example.com", 404, "missing", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as get:
            self.assertIsNone(HttpClient().get_optional("https://example.com"))
        self.assertEqual(get.call_count, 1)

    def test_oversized_source_rejected(self):
        response = Mock()
        response.geturl.return_value = "https://example.com"
        response.read.return_value = b"12345"
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("urllib.request.urlopen", return_value=response), self.assertRaises(SourceError):
            HttpClient(max_bytes=4).get("https://example.com")


class FakeClient:
    fail_on = ""
    missing_year = 0

    def get_optional(self, url):
        year = int(url.rsplit("/", 1)[1].removesuffix(".json"))
        if year == self.missing_year:
            return None
        payload = json.loads((ROOT / "data" / "holidays" / f"{year}.json").read_text())
        for day in payload["days"]:
            day["isOffDay"] = day.pop("is_off_day")
        return FetchResult(json.dumps(payload).encode(), url)

    def get(self, url):
        if self.fail_on and self.fail_on in url:
            raise SourceError("simulated final-source failure")
        if "24SolarTerms_" in url:
            year = int(url.rsplit("_", 1)[1][:4])
            return FetchResult(solar_raw(year), url)
        year = int(url.rsplit("/T", 1)[1][:4])
        return FetchResult(lunar_raw(year), url)


class SourceUpdateTests(unittest.TestCase):
    def test_final_source_failure_does_not_write_any_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sentinel = root / "data" / "holidays" / "2025.json"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_text('{"keep": "unchanged"}')
            client = FakeClient()
            client.fail_on = "24SolarTerms_2028"
            with self.assertRaises(SourceError):
                fetch_all(root, date(2026, 10, 21), client)
            self.assertEqual(sentinel.read_text(), '{"keep": "unchanged"}')
            self.assertEqual(list(root.rglob("*.json")), [sentinel])

    def test_future_404_must_not_erase_existing_published_schedule(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data" / "holidays" / "2027.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"papers":["official"],"days":[{"published":true}]}')
            before = path.read_bytes()
            client = FakeClient()
            client.missing_year = 2027
            with self.assertRaisesRegex(SourceError, "erase"):
                fetch_all(root, date(2026, 10, 21), client)
            self.assertEqual(path.read_bytes(), before)

    def test_successful_update_keeps_unannounced_year_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fetch_all(root, date(2026, 10, 21), FakeClient())
            self.assertEqual(len(list(root.rglob("*.json"))), 13)
            self.assertEqual(json.loads((root / "data/holidays/2027.json").read_text())["days"], [])

    def test_config_and_generator_changes_invalidate_state_without_daily_churn(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("data", "config", "china_calendar"):
                (root / folder).mkdir()
            config = root / "config" / "test.json"
            config.write_text("{}")
            update_source_state(root)
            state = root / "data" / "source-state.json"
            first = state.read_bytes()
            update_source_state(root)
            self.assertEqual(first, state.read_bytes())
            config.write_text('{"new":true}')
            update_source_state(root)
            self.assertNotEqual(json.loads(first)["source_digest"], json.loads(state.read_bytes())["source_digest"])
            digest = json.loads(state.read_bytes())["source_digest"]
            (root / "china_calendar" / "test.py").write_text("# generator changed")
            update_source_state(root)
            self.assertNotEqual(digest, json.loads(state.read_bytes())["source_digest"])


class FeedRegressionTests(unittest.TestCase):
    def test_ongoing_holiday_preserves_full_span_and_uid(self):
        today = date(2026, 10, 3)
        full = next(e for e in holiday_events(ROOT, today, False) if e.start == date(2026, 10, 1))
        filtered = next(e for e in holiday_events(ROOT, today, True) if e.kind == "holiday")
        self.assertEqual(filtered, full)
        self.assertFalse(any(e.uid == full.uid for e in holiday_events(ROOT, date(2026, 10, 8), True)))

    def test_cross_year_notice_duplicates_merge_into_one_holiday(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "data" / "holidays"
            folder.mkdir(parents=True)
            for year in (2025, 2026):
                (folder / f"{year}.json").write_text(json.dumps({
                    "papers": [PAPER], "days": [
                        {"date": "2025-12-31", "name": "元旦", "is_off_day": True},
                        {"date": "2026-01-01", "name": "元旦", "is_off_day": True},
                    ],
                }))
            events = holiday_events(root, date(2026, 1, 1), False)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].end, date(2026, 1, 2))

    def test_rolling_window_excludes_old_year_and_next_year_nines(self):
        groups = collect_events(ROOT, date(2028, 1, 1), False)
        self.assertTrue(all(2027 <= event.start.year <= 2030 for event in groups["calendar"]))
        groups = collect_events(ROOT, date(2026, 10, 21), False)
        self.assertFalse(any(event.start.year == 2029 for event in groups["calendar"]))
        self.assertTrue(any(event.summary == "时令 · 三九" and event.start == date(2025, 1, 8)
                            for event in groups["calendar"]))

    def test_new_feeds_have_expected_scope_and_existing_full_feed_has_no_duplicates(self):
        groups = collect_events(ROOT, date(2026, 10, 21), False)
        self.assertEqual({e.kind for e in groups["essential"]}, {"holiday", "workday", "solar_term", "traditional"})
        self.assertEqual({e.kind for e in groups["health"]}, {"health"})
        self.assertEqual({e.kind for e in groups["traditional"]}, {"traditional"})
        self.assertEqual(len(groups["calendar"]), len({e.uid for e in groups["calendar"]}))

    def test_timed_event_on_first_day_is_in_window(self):
        start = datetime.fromisoformat("2026-01-01T12:00:00+08:00")
        event = Event("test", "test", "solar_term", start, start + timedelta(minutes=1))
        self.assertTrue(overlaps(event, date(2026, 1, 1), date(2026, 1, 2)))
        self.assertFalse(overlaps(event, date(2026, 1, 2), date(2026, 1, 3)))

    def test_malformed_ics_events_rejected_and_no_feed_partially_written(self):
        event = Event("test", "test", "holiday", date(2026, 1, 1), date(2026, 1, 2))
        for bad in (replace(event, end=event.start), replace(event, url="https://example.com\nBEGIN:VALARM")):
            with self.assertRaises(ValueError):
                render_calendar("holidays", [bad], STAMP)
        with self.assertRaises(ValueError):
            render_calendar("holidays", [event, event], STAMP)
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                write_calendars(Path(temporary), {"holidays": [event], "calendar": [event, event]}, STAMP)
            self.assertEqual(list(Path(temporary).rglob("*.ics")), [])

    def test_all_feeds_are_deterministic_folded_and_have_unique_uids(self):
        groups = collect_events(ROOT, date(2026, 10, 21), False)
        for name, events in groups.items():
            with self.subTest(feed=name):
                first = render_calendar(name, events, STAMP)
                self.assertEqual(first, render_calendar(name, list(reversed(events)), STAMP))
                self.assertNotIn(b"\n", first.replace(b"\r\n", b""))
                self.assertTrue(all(len(line) <= 75 for line in first.split(b"\r\n")))


class DateQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups = collect_events(ROOT, date(2026, 10, 21), False)

    def test_day_status_distinguishes_weekends_workdays_and_overrides(self):
        examples = {
            date(2026, 2, 14): "makeup_workday", date(2026, 10, 3): "holiday",
            date(2026, 10, 18): "weekend", date(2026, 10, 21): "workday",
            date(2027, 1, 1): "unknown",
        }
        for day, status in examples.items():
            with self.subTest(day=day):
                record = day_record(ROOT, day, self.groups, "essential")
                self.assertEqual(record["day_type"], status)

    def test_query_includes_solar_term_time_and_lunar_date(self):
        record = day_record(ROOT, date(2026, 10, 8), self.groups, "essential")
        self.assertTrue(any(e["start"] == "2026-10-08T14:29:00+08:00" for e in record["events"]))
        self.assertIsNotNone(record["lunar"])

    def test_query_json_is_read_only_and_does_not_fetch(self):
        before = (ROOT / "data/source-state.json").read_bytes()
        with patch("china_calendar.cli.fetch_all") as fetch, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--root", str(ROOT), "--date", "2026-02-14", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["day_type"], "makeup_workday")
        fetch.assert_not_called()
        self.assertEqual((ROOT / "data/source-state.json").read_bytes(), before)

    def test_upcoming_query_includes_ongoing_holiday_and_crosses_year(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--root", str(ROOT), "--today", "2026-12-31", "--upcoming", "3", "--json"]), 0)
        self.assertEqual([r["date"] for r in json.loads(output.getvalue())], ["2026-12-31", "2027-01-01", "2027-01-02"])

    def test_missing_data_is_clear_and_returns_nonzero(self):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertEqual(main(["--root", "/nonexistent", "--offline"]), 1)
        self.assertIn("找不到日历数据目录", output.getvalue())

    def test_offline_rebuild_does_not_require_existing_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("data", "config", "china_calendar"):
                shutil.copytree(ROOT / folder, root / folder)
            (root / "data/source-state.json").unlink()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--root", str(root), "--offline", "--today", "2026-10-21"]), 0)
            first = {p.name: p.read_bytes() for p in (root / "calendars").glob("*.ics")}
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--root", str(root), "--offline", "--today", "2026-10-21"]), 0)
            self.assertEqual(first, {p.name: p.read_bytes() for p in (root / "calendars").glob("*.ics")})
            self.assertEqual(len(first), 9)

    def test_check_detects_stale_feeds_without_modifying_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for folder in ("data", "config", "china_calendar"):
                shutil.copytree(ROOT / folder, root / folder)
            args = ["--root", str(root), "--today", "2026-10-21"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args + ["--offline"]), 0)
                self.assertEqual(main(args + ["--check"]), 0)
                path = root / "calendars/essential.ics"
                path.write_bytes(b"corrupted")
                before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
                self.assertEqual(main(args + ["--check"]), 1)
                self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_custom_output_does_not_change_canonical_feeds_or_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "feeds"
            before = (ROOT / "data/source-state.json").read_bytes()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([
                    "--root", str(ROOT), "--offline", "--today", "2026-10-03",
                    "--future-holidays-only", "--output", str(destination),
                ]), 0)
            self.assertEqual((ROOT / "data/source-state.json").read_bytes(), before)
            self.assertTrue((destination / ".source-state.json").exists())


if __name__ == "__main__":
    unittest.main()
