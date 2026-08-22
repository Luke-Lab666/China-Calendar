from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .events import collect_events
from .ical import write_calendars
from .sources import fetch_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="更新并生成中国日历 ICS 订阅")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--offline", action="store_true", help="只用仓库内已有数据生成")
    parser.add_argument(
        "--future-holidays-only",
        action="store_true",
        help="不在生成结果中保留已过去的法定放假和调休事件",
    )
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    if args.offline:
        import json

        state = json.loads((root / "data" / "source-state.json").read_text(encoding="utf-8"))
        generated_at = state["generated_at"]
    else:
        generated_at = fetch_all(root, args.today)
    groups = collect_events(root, args.today, args.future_holidays_only)
    write_calendars(root, groups, generated_at)
    for name, events in groups.items():
        print(f"{name}: {len(events)} events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

