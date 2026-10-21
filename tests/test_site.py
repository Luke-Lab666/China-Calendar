from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from china_calendar.site import build_site, site_data

ROOT = Path(__file__).resolve().parents[1]


class SiteTests(unittest.TestCase):
    def test_export_matches_real_dates_and_never_marks_unpublished_year_as_off(self):
        data = site_data(ROOT, date(2026, 10, 21))
        self.assertEqual(data["lunar"]["2026-02-14"], [12, 27, False])
        self.assertEqual(data["holidays_published"], [2025, 2026])
        self.assertTrue(any(e["kind"] == "workday" and e["start"] == "2026-02-14" for e in data["events"]))
        self.assertNotIn(2027, data["holidays_published"])
        self.assertEqual(len({e["uid"] for e in data["events"]}), len(data["events"]))

    def test_build_is_self_contained_and_serves_identical_subscription_bytes(self):
        class Assets(HTMLParser):
            paths = []

            def handle_starttag(self, tag, attrs):
                for name, value in attrs:
                    if name in {"src", "href"} and value.startswith("./"):
                        self.paths.append(value[2:])

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            build_site(ROOT, output, date(2026, 10, 21))
            page = Assets()
            page.feed((output / "index.html").read_text(encoding="utf-8"))
            for asset in page.paths:
                self.assertTrue((output / asset).is_file(), asset)
            self.assertTrue((output / "calendar.mjs").is_file())
            self.assertTrue((output / ".nojekyll").exists())
            data = json.loads((output / "data.json").read_text())
            self.assertEqual(len(data["feeds"]), 9)
            for feed in data["feeds"]:
                path = output / "calendars" / f"{feed['id']}.ics"
                self.assertEqual(path.read_bytes(), (ROOT / "calendars" / path.name).read_bytes())

    def test_build_refuses_to_overwrite_source_directories(self):
        for folder in (".", "web", "data", "calendars", "china_calendar"):
            with self.subTest(folder=folder), self.assertRaises(ValueError):
                build_site(ROOT, ROOT / folder, date(2026, 10, 21))


if __name__ == "__main__":
    unittest.main()
