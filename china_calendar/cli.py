from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from .events import SHANGHAI, collect_events
from .ical import CALENDAR_NAMES, render_calendar, write_calendars
from .query import day_record, format_day
from .sources import SourceError, fetch_all, update_source_state


def _days(value: str) -> int:
    days = int(value)
    if not 1 <= days <= 366:
        raise argparse.ArgumentTypeError("天数必须在 1 到 366 之间")
    return days


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="更新中国日历订阅，或离线查询日期与近期安排")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="仓库数据目录")
    parser.add_argument("--offline", action="store_true", help="只用仓库内已有数据生成")
    parser.add_argument("--check", action="store_true", help="离线检查订阅是否与当前代码和数据一致，不写文件")
    parser.add_argument("--output", type=Path, help="日历输出目录，默认 ROOT/calendars")
    parser.add_argument(
        "--future-holidays-only", action="store_true",
        help="仅保留尚未结束的法定假期和补班，保留完整假期及原 UID",
    )
    parser.add_argument("--today", type=date.fromisoformat, default=datetime.now(SHANGHAI).date())
    query = parser.add_mutually_exclusive_group()
    query.add_argument("--date", type=date.fromisoformat, help="查询指定日期（仅使用本地数据）")
    query.add_argument("--upcoming", type=_days, metavar="DAYS", help="查询从今天起的 N 天（离线）")
    parser.add_argument("--feed", choices=tuple(CALENDAR_NAMES), default="essential", help="查询的订阅，默认精简版")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出日期查询结果")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    querying = args.date is not None or args.upcoming is not None
    if args.json and not querying:
        parser.error("--json 需要配合 --date 或 --upcoming")
    if querying and (args.output or args.future_holidays_only or args.check):
        parser.error("日期查询不能使用 --output、--check 或 --future-holidays-only")
    try:
        if not (root / "data" / "lunar").is_dir():
            raise SourceError(f"找不到日历数据目录：{root}；请在仓库目录运行或使用 --root")
        if querying:
            start = args.date or args.today
            days = args.upcoming or 1
            if not 2025 <= start.year <= 9996:
                raise ValueError("日期查询支持 2025 至 9996 年")
            groups = collect_events(root, start, False)
            records = [day_record(root, start + timedelta(days=i), groups, args.feed) for i in range(days)]
            if args.json:
                print(json.dumps(records[0] if args.date else records, ensure_ascii=False, indent=2))
            else:
                print("\n\n".join(format_day(record) for record in records))
            return 0
        if not 2025 <= args.today.year <= 9996:
            raise ValueError("生成年份支持 2025 至 9996 年")
        if not (args.offline or args.check):
            fetch_all(root, args.today)
        groups = collect_events(root, args.today, args.future_holidays_only)
        if not groups["solar-terms"]:
            raise SourceError("生成范围内没有节气数据，请先联网更新数据")
        options = {
            "start_year": max(2025, args.today.year - 1),
            "end_year": args.today.year + 2,
            "future_holidays_from": args.today.isoformat() if args.future_holidays_only else None,
        }
        output = args.output.resolve() if args.output else root / "calendars"
        state_path = output / ".source-state.json" if args.output else None
        generated_at = update_source_state(
            root, build_options=options, state_path=state_path, persist=not args.check,
        )
        if args.check:
            stale = [
                name for name, events in groups.items()
                if not (output / f"{name}.ics").exists()
                or (output / f"{name}.ics").read_bytes() != render_calendar(name, events, generated_at)
            ]
            if stale:
                raise SourceError(f"订阅需要重新生成：{', '.join(stale)}；请运行 --offline")
            print(f"检查通过：{len(groups)} 个订阅与代码、配置及源数据一致。")
            return 0
        write_calendars(root, groups, generated_at, args.output)
        for name, events in groups.items():
            years = sorted({event.start.year for event in events})
            coverage = f"{years[0]}–{years[-1]}" if years else "暂无已公布数据"
            print(f"{name}: {len(events)} events ({coverage})")
        holiday_years = []
        for year in range(options["start_year"], options["end_year"] + 1):
            path = root / "data" / "holidays" / f"{year}.json"
            if not path.exists() or not json.loads(path.read_text(encoding="utf-8")).get("days"):
                holiday_years.append(str(year))
        if holiday_years:
            print(f"提示：{', '.join(holiday_years)} 年暂无正式放假调休数据，未预测假期。", file=sys.stderr)
        return 0
    except (SourceError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

