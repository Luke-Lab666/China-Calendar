"""Build the GitHub Pages site from the same data as the subscription feeds."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from .events import SHANGHAI, collect_events
from .ical import CALENDAR_NAMES, render_calendar
from .query import event_record
from .storage import write_if_changed


def site_data(root: Path, today: date) -> dict:
    state = json.loads((root / "data/source-state.json").read_text(encoding="utf-8"))
    groups = collect_events(root, today, False)
    first, last = max(2025, today.year - 1), today.year + 2
    lunar = {}
    for path in sorted((root / "data/lunar").glob("*.json")):
        if first <= int(path.stem) <= last:
            for row in json.loads(path.read_text(encoding="utf-8"))["days"]:
                lunar[row["date"]] = [row["lunar_month"], row["lunar_day"], row["leap_month"]]
    published = []
    for path in sorted((root / "data/holidays").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["papers"] and payload["days"] and first <= payload["year"] <= last:
            published.append(payload["year"])
    return {
        "schema": 1,
        "generated_at": state["generated_at"],
        "range": {"start_year": first, "end_year": last},
        "holidays_published": published,
        "lunar": lunar,
        "events": [event_record(event) for event in groups["calendar"]],
        "feeds": [{"id": name, "name": CALENDAR_NAMES[name], "count": len(events)}
                  for name, events in groups.items()],
    }


def build_site(root: Path, output: Path, today: date) -> None:
    root, output = root.resolve(), output.resolve()
    # An output must never overwrite repository sources or calendar inputs.
    protected = [root / folder for folder in ("web", "data", "china_calendar", "config", "tests", "calendars", ".github", ".git")]
    if output == root or output in root.parents or any(output == p or p in output.parents for p in protected):
        raise ValueError("The site output must be a separate build directory")
    state = json.loads((root / "data/source-state.json").read_text(encoding="utf-8"))
    groups = collect_events(root, today, False)
    output.mkdir(parents=True, exist_ok=True)
    for path in (root / "web").rglob("*"):
        if path.is_file():
            target = output / path.relative_to(root / "web")
            write_if_changed(target, path.read_bytes())
    for name, events in groups.items():
        write_if_changed(output / "calendars" / f"{name}.ics", render_calendar(name, events, state["generated_at"]))
    # This directory contains build-owned feeds only. Reusing a build directory
    # must not accidentally republish a subscription removed from the project.
    for path in (output / "calendars").glob("*.ics"):
        if path.stem not in groups:
            path.unlink()
    content = json.dumps(site_data(root, today), ensure_ascii=False, separators=(",", ":")) + "\n"
    write_if_changed(output / "data.json", content.encode("utf-8"))
    write_if_changed(output / ".nojekyll", b"")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the China Calendar GitHub Pages site")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("_site"))
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(SHANGHAI).date())
    args = parser.parse_args(argv)
    build_site(args.root, args.output, args.today)
    print(f"Site built: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
