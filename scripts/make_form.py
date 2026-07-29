#!/usr/bin/env python3
"""Estimate PDF in, signed SAISD form out. One command.

Usage:
    make_form.py path/to/estimate.pdf
    make_form.py estimate.pdf --form-date 7/22/2026 -o output/form.pdf
    make_form.py estimate.pdf --no-sign        # produce a draft to review

Anything the extractor is unsure about is printed as a WARNING. Read them
before sending the form.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_quote import ExtractError, build_payload   # noqa: E402
from fill_form import FillError, fill                   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("estimate", help="path to the Get Complete estimate PDF")
    ap.add_argument("-o", "--output", help="output PDF path")
    ap.add_argument("--form-date", help="date to put on the form (default: today)")
    ap.add_argument("--no-sign", action="store_true", help="leave the signature line blank")
    ap.add_argument("--show-payload", action="store_true",
                    help="print the extracted values before filling")
    args = ap.parse_args(argv)

    estimate = Path(args.estimate)
    if not estimate.exists():
        print(f"ERROR: no such file: {estimate}", file=sys.stderr)
        return 1

    try:
        payload, warnings = build_payload(estimate, args.form_date)
    except ExtractError as exc:
        print(f"ERROR reading the estimate: {exc}", file=sys.stderr)
        return 1

    if args.show_payload:
        print(json.dumps(payload, indent=2))

    if args.output:
        out = Path(args.output)
    else:
        campus = (payload.get("campus_name") or "quote").replace(" ", "-")
        out = ROOT / "output" / f"SAISD-RFQ-{campus}-{date.today():%Y%m%d}.pdf"

    try:
        warnings += fill(payload, out, sign=not args.no_sign)
    except FillError as exc:
        print(f"ERROR filling the form: {exc}", file=sys.stderr)
        return 1

    print(f"\n  Campus   {payload.get('campus_name')}")
    print(f"  Quote #  {payload.get('bid_contract_number')}")
    print(f"  Items    {len(payload['line_items'])}")
    for item in payload["line_items"]:
        print(f"             {item['description']:<40} {item['amount']:>12}")
    print(f"  Total    {payload.get('total_price')}")
    print(f"\n  -> {out}")

    if warnings:
        print("\n  Check before sending:")
        for w in warnings:
            print(f"    - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
