#!/usr/bin/env python3
"""Read a Get Complete estimate PDF and emit the payload fill_form.py wants.

Usage:
    extract_quote.py estimate.pdf [-o payload.json]

The estimate layout is columnar and machine-readable, so everything is located
by column geometry rather than by scraping flowed text:

    TYPE        DESCRIPTION        QTY     PRICE     TOTAL

Amounts come from the TOTAL column, never PRICE, because PRICE is a unit rate.

Repeated line items are deliberately NOT merged. Two "Plumbing Labor" rows at
8 hours each means two techs on the job; collapsing them into one 16-hour row
would destroy the crew-size information the scheduler relies on.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber

ROW_TOLERANCE = 3.0          # points; words within this are the same visual row
MONEY_RE = re.compile(r"^\$?-?[\d,]+(?:\.\d{2})?$")
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


class ExtractError(Exception):
    """Raised when the estimate does not look like the expected layout."""


def group_rows(words, tolerance=ROW_TOLERANCE):
    """Group words into visual rows keyed by their top coordinate."""
    rows: list[tuple[float, list]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        for i, (top, bucket) in enumerate(rows):
            if abs(w["top"] - top) <= tolerance:
                bucket.append(w)
                break
        else:
            rows.append((w["top"], [w]))
    return [(top, sorted(b, key=lambda w: w["x0"])) for top, b in rows]


def col_text(row, x0, x1) -> str:
    """Join the words whose centre falls inside a column band."""
    parts = [w["text"] for w in row if x0 <= (w["x0"] + w["x1"]) / 2 < x1]
    return " ".join(parts).strip()


def money(text: str) -> Decimal:
    return Decimal(text.replace("$", "").replace(",", "").strip())


def find_header(rows):
    """Locate the service-table header and return its column x-centres."""
    for idx, (top, row) in enumerate(rows):
        labels = {w["text"].upper(): w for w in row}
        if {"DESCRIPTION", "QTY", "PRICE", "TOTAL"} <= set(labels):
            # TYPE is included so DESCRIPTION's band has a left neighbour and
            # does not swallow the TYPE column.
            keys = [k for k in ("TYPE", "DESCRIPTION", "QTY", "PRICE", "TOTAL")
                    if k in labels]
            centres = {
                key: (labels[key]["x0"] + labels[key]["x1"]) / 2 for key in keys
            }
            return idx, top, centres
    raise ExtractError(
        "could not find the service table header (DESCRIPTION / QTY / PRICE / TOTAL). "
        "The estimate template may have changed."
    )


def column_bands(centres, page_width):
    """Turn column centres into non-overlapping x bands."""
    ordered = sorted(centres.items(), key=lambda kv: kv[1])
    bands = {}
    for i, (name, cx) in enumerate(ordered):
        left = 0.0 if i == 0 else (ordered[i - 1][1] + cx) / 2
        right = page_width if i == len(ordered) - 1 else (ordered[i + 1][1] + cx) / 2
        bands[name] = (left, right)
    # DESCRIPTION starts after the TYPE column, which has no useful data for us.
    return bands


def extract_line_items(pdf) -> tuple[list[dict], Decimal | None]:
    items: list[dict] = []
    quote_total: Decimal | None = None
    bands = None
    page_width = pdf.pages[0].width

    for page_no, page in enumerate(pdf.pages):
        rows = group_rows(page.extract_words())
        start = 0
        if bands is None:
            try:
                idx, _, centres = find_header(rows)
            except ExtractError:
                continue                      # table has not started yet
            bands = column_bands(centres, page_width)
            start = idx + 1

        for _, row in rows[start:]:
            joined = " ".join(w["text"] for w in row).strip()
            upper = joined.upper()

            if upper.startswith("QUOTE TOTAL"):
                nums = [w["text"] for w in row if MONEY_RE.match(w["text"])]
                if nums:
                    quote_total = money(nums[-1])
                return items, quote_total
            if upper.startswith(("SUB-TOTAL", "SUBTOTAL", "TAX")):
                continue

            desc = col_text(row, *bands["DESCRIPTION"])
            total = col_text(row, *bands["TOTAL"])
            if not desc or not MONEY_RE.match(total):
                continue

            items.append({
                "description": desc.strip("*").strip(),
                "amount": str(money(total)),
                "_qty": col_text(row, *bands["QTY"]),
                "_unit_price": col_text(row, *bands["PRICE"]),
            })

    return items, quote_total


def extract_header(pdf) -> dict:
    """Pull quote number, quote date and campus name from the first page."""
    page = pdf.pages[0]
    rows = group_rows(page.extract_words())
    out: dict[str, str] = {}

    # QUOTE / QUOTE DATE sit in the right-hand block; their values are on the
    # next row down.
    for i, (top, row) in enumerate(rows):
        texts = [w["text"].upper() for w in row]
        if "QUOTE" in texts and "DATE" in texts:
            # The values may not land on the very next visual row - the
            # BILL TO / JOB ADDRESS blocks interleave with them - so scan a
            # few rows down through the right-hand column.
            for _, nxt in rows[i + 1:i + 5]:
                for w in nxt:
                    if w["x0"] <= 300:
                        continue
                    if DATE_RE.match(w["text"]):
                        out.setdefault("quote_date", w["text"])
                    elif re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{3,}", w["text"]):
                        out.setdefault("bid_contract_number", w["text"])
                if "quote_date" in out and "bid_contract_number" in out:
                    break
            break

    # Campus name is the first line of the JOB ADDRESS column.
    for i, (top, row) in enumerate(rows):
        job = [w for w in row if w["text"].upper() == "JOB"]
        addr = [w for w in row if w["text"].upper() == "ADDRESS"]
        if job and addr:
            left = job[0]["x0"] - 5
            right = left + 180
            for _, nxt in rows[i + 1:]:
                name = col_text(nxt, left, right)
                if name:
                    out["campus_name"] = name
                    break
            break

    return out


def build_payload(pdf_path: Path, form_date: str | None) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        header = extract_header(pdf)
        items, quote_total = extract_line_items(pdf)

    if not items:
        raise ExtractError("no line items found in the estimate")

    for key, label in (("campus_name", "campus name"),
                       ("bid_contract_number", "quote number")):
        if not header.get(key):
            warnings.append(f"could not read the {label} from the estimate")

    subtotal = sum(Decimal(i["amount"]) for i in items)
    if quote_total is not None and quote_total != subtotal:
        warnings.append(
            f"estimate's QUOTE TOTAL is {quote_total} but its line items sum to "
            f"{subtotal} - check for tax or a discount line"
        )

    today = date.today()
    payload = {
        "date": form_date or f"{today.month}/{today.day}/{today.year}",
        "campus_name": header.get("campus_name", ""),
        "bid_contract_number": header.get("bid_contract_number", ""),
        "line_items": [
            {"description": i["description"], "amount": i["amount"]} for i in items
        ],
        "total_price": str(quote_total) if quote_total is not None else None,
        "_source_estimate": pdf_path.name,
        "_quote_date": header.get("quote_date"),
    }
    return payload, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("estimate", help="path to the estimate PDF")
    ap.add_argument("-o", "--output", help="write payload JSON here (default: stdout)")
    ap.add_argument("--form-date", help="date for the form (default: today)")
    args = ap.parse_args(argv)

    try:
        payload, warnings = build_payload(Path(args.estimate), args.form_date)
    except ExtractError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n")
        print(f"wrote {args.output}")
    else:
        print(text)

    for w in warnings:
        print(f"  WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
