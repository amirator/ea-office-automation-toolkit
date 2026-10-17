"""Command-line interface: python -m toolkit <command> [options]."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from toolkit import __version__
from toolkit.common import OUTPUT_DIR, SAMPLE_BANNER, SAMPLE_DIR


def _ics_arg(values: list[str] | None) -> dict[str, str]:
    out = {}
    for v in values or []:
        if "=" not in v:
            raise SystemExit(f"--ics expects 'Attendee Name=path/to/file.ics', got {v!r}")
        name, path = v.split("=", 1)
        out[name.strip()] = path.strip()
    return out


def _add_schedule_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--attendees", default=SAMPLE_DIR / "attendees.csv", help="CSV of attendees (name, timezone, hours, work_days)")
    p.add_argument("--busy", default=SAMPLE_DIR / "busy.csv", help="CSV of busy blocks (attendee,start,end,title)")
    p.add_argument("--ics", action="append", metavar="NAME=FILE", help="Busy times from an .ics export; repeatable")
    p.add_argument("--start", type=date.fromisoformat, default=date(2026, 11, 1), help="First day to search (YYYY-MM-DD)")
    p.add_argument("--end", type=date.fromisoformat, default=date(2026, 11, 5), help="Last day to search (YYYY-MM-DD)")
    p.add_argument("--duration", type=int, default=60, help="Meeting length in minutes (default 60)")
    p.add_argument("--tz", default="Asia/Riyadh", help="Organiser time zone (default Asia/Riyadh)")
    p.add_argument("--no-gulf-weekend", action="store_true", help="Allow Friday/Saturday (organiser time)")
    p.add_argument("--prayer-city", default="jeddah", help="City for prayer buffers (jeddah, riyadh, dammam, makkah, dubai, doha)")
    p.add_argument("--prayer-buffer", type=int, default=20, help="Minutes kept free after Dhuhr/Asr/Maghrib; 0 to disable")
    p.add_argument("--results", type=int, default=5, help="Number of slots to propose")


def _slots(args):
    from toolkit.scheduler import find_slots, load_attendees

    ics = _ics_arg(args.ics)
    if args.ics is None and Path(args.attendees).resolve() == (SAMPLE_DIR / "attendees.csv").resolve():
        ics = {"Claire Bennett": SAMPLE_DIR / "claire_bennett.ics"}
    people = load_attendees(args.attendees, args.busy, ics)
    slots = find_slots(people, args.start, args.end, args.duration, args.tz, gulf_weekend=not args.no_gulf_weekend,
                       prayer_city=args.prayer_city if args.prayer_buffer > 0 else None,
                       prayer_buffer_min=args.prayer_buffer, max_results=args.results)
    return people, slots


def _print_slots(people, slots, args) -> None:
    print(f"Proposed {args.duration}-minute slots ({args.tz}) for {len(people)} attendees, "
          f"{args.start:%d %b} - {args.end:%d %b %Y}")
    rules = ["working hours + work week per attendee", "busy calendars"]
    if not args.no_gulf_weekend:
        rules.append("Gulf weekend (Fri-Sat) excluded")
    if args.prayer_buffer > 0:
        rules.append(f"{args.prayer_buffer}-min prayer buffers ({args.prayer_city.title()})")
    print("Rules: " + "; ".join(rules))
    if not slots:
        print("\nNo slot satisfies every constraint. Try a longer window, shorter meeting or fewer attendees.")
        return
    for n, s in enumerate(slots, 1):
        print(f"\n [{n}] {s.start:%a %d %b %H:%M}-{s.end:%H:%M}   " + ("  ".join(s.notes)))
        for name, local in s.local_times.items():
            print(f"      {name:<20} {local}")


def cmd_slots(args) -> int:
    people, slots = _slots(args)
    _print_slots(people, slots, args)
    return 0 if slots else 1


def cmd_agenda(args) -> int:
    from toolkit.agenda import generate_agenda

    people, slots = _slots(args)
    _print_slots(people, slots, args)
    if not slots:
        return 1
    if not 1 <= args.pick <= len(slots):
        raise SystemExit(f"--pick must be between 1 and {len(slots)}")
    files = generate_agenda(args.brief, slots[args.pick - 1], people, slots, args.out, sample=not args.real, pdf=args.pdf)
    print(f"\nAgenda for slot [{args.pick}] written:")
    for k, v in files.items():
        print(f"  {k:<9} {v}")
    return 0


def cmd_expenses(args) -> int:
    from toolkit.expenses import generate, text_summary

    res = generate(args.expenses, args.trips, args.rates, args.policy, args.out, sample=not args.real)
    print(text_summary(res["data"]))
    print(f"\n  workbook  {res['workbook']}\n  summary   {res['summary']}")
    return 0


def cmd_kpi(args) -> int:
    from toolkit.kpi import commentary, load_kpis, render

    res = render(load_kpis(args.csv), args.out, args.period, sample=not args.real)
    c = res["counts"]
    print(f"KPI pack {res['period']}: {c['Green']} Green, {c['Amber']} Amber, {c['Red']} Red")
    for r in res["rows"]:
        if r["status"] != "Green":
            print(f"  [{r['status']}] {commentary(r)}")
    print(f"\n  pdf  {res['pdf']}\n  png  {res['png']}")
    return 0


def cmd_demo(args) -> int:
    print(f"*** {SAMPLE_BANNER} ***\n")
    base = Path(args.out)
    print("=" * 72 + "\n1) Meeting scheduler + agenda\n" + "=" * 72)
    ns = build_parser().parse_args(["agenda", "--out", str(base / "agenda"), "--pdf"])
    cmd_agenda(ns)
    print("\n" + "=" * 72 + "\n2) Expense / travel tracker\n" + "=" * 72)
    cmd_expenses(build_parser().parse_args(["expenses", "--out", str(base / "expenses")]))
    print("\n" + "=" * 72 + "\n3) KPI pack\n" + "=" * 72)
    cmd_kpi(build_parser().parse_args(["kpi", "--out", str(base / "kpi")]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m toolkit",
                                description="Executive-office automation: scheduling, agendas, expenses and KPI packs.")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("slots", help="Propose meeting slots across time zones")
    _add_schedule_args(s)
    s.set_defaults(func=cmd_slots)

    a = sub.add_parser("agenda", help="Propose slots and write a timed agenda (DOCX/MD/ICS, optional PDF)")
    _add_schedule_args(a)
    a.add_argument("--brief", default=SAMPLE_DIR / "meeting_brief.json", help="Meeting brief JSON (title, items...)")
    a.add_argument("--pick", type=int, default=1, help="Which proposed slot to build the agenda for (default 1)")
    a.add_argument("--pdf", action="store_true", help="Also export PDF (needs LibreOffice)")
    a.add_argument("--out", default=OUTPUT_DIR / "agenda", help="Output folder")
    a.add_argument("--real", action="store_true", help="Omit the SAMPLE DATA banner (for your own data)")
    a.set_defaults(func=cmd_agenda)

    e = sub.add_parser("expenses", help="Build the expense/travel Excel tracker and summary")
    e.add_argument("--expenses", default=SAMPLE_DIR / "expenses.csv")
    e.add_argument("--trips", default=SAMPLE_DIR / "trips.csv")
    e.add_argument("--rates", default=SAMPLE_DIR / "fx_rates.csv")
    e.add_argument("--policy", default=SAMPLE_DIR / "policy_limits.csv")
    e.add_argument("--out", default=OUTPUT_DIR / "expenses")
    e.add_argument("--real", action="store_true", help="Omit the SAMPLE DATA banner")
    e.set_defaults(func=cmd_expenses)

    k = sub.add_parser("kpi", help="Render a one-page executive KPI pack (PDF + PNG)")
    k.add_argument("--csv", default=SAMPLE_DIR / "kpis.csv")
    k.add_argument("--period", help="Reporting month YYYY-MM (default: latest in the file)")
    k.add_argument("--out", default=OUTPUT_DIR / "kpi")
    k.add_argument("--real", action="store_true", help="Omit the SAMPLE DATA banner")
    k.set_defaults(func=cmd_kpi)

    d = sub.add_parser("demo", help="Run all three tools on the bundled sample data")
    d.add_argument("--out", default=OUTPUT_DIR)
    d.set_defaults(func=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
