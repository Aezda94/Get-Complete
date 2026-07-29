#!/usr/bin/env python3
"""Fill the SAISD Request for Quote form from a quote payload.

Usage:
    fill_form.py payload.json [-o output.pdf]
    fill_form.py -                      # read JSON from stdin

Reproduces Acrobat's own output conventions, verified against the signed
examples in examples/completed-forms/:

  * Amount fields store a raw value ("1140") but *display* a formatted,
    right-aligned one ("1,140.00"), because the form carries
    AFNumber_Format(2, 0, ...) scripts and /Q 2. Appearance streams are built
    here so the result renders identically in viewers that do not run
    JavaScript (Preview, Chrome, most print paths).
  * Text fields render left-aligned at /Helv 8.118.

Field mapping is documented in
.claude/skills/quote-form/references/field-map.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    TextStringObject,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "form-template" / "SAISD-Quote-Form-fillable.pdf"
SIGNATURE = ROOT / "assets" / "signature.png"
CONSTANTS = ROOT / "assets" / "constants.json"

MAX_LINE_ITEMS = 15

# Matches where the signature sat in both signed examples
# (LBE2 394.8-547.1, JBQF 382.4-534.6; both 152.2 x 45.9).
SIG_BOX = fitz.Rect(392.0, 128.9, 544.2, 174.8)

# Acrobat's own typography for this form, read out of the example appearance
# streams rather than guessed.
FONT_SIZE = 8.118
BASELINE_RATIO = 0.2676   # baseline y as a fraction of box height
SIDE_PAD = 2.0

PAYMENT_BOND_THRESHOLD = Decimal("25000.00")
PERFORMANCE_BOND_THRESHOLD = Decimal("100000.00")

HEADER_FIELDS = {
    "date": "Date",
    "campus_name": "Campus Name",
    "bid_contract_number": "BidContract Number",
    "company_name": "Company Name",
    "rep_name": "Company Representative Name",
    "rep_email": "Company Representative email",
    "rep_phone": "Company Representative Phone",
}

TOTAL_FIELD = "Total Price"
PAYMENT_BOND_FIELD = "undefined_16"
PERFORMANCE_BOND_FIELD = "undefined_17"
GRAND_TOTAL_FIELD = "Grand Total Price"


def amount_field(row: int) -> str:
    """Row 1's amount widget is named 'undefined'; rows 2-15 add a suffix.

    Verified against widget geometry, not field order, which is unreliable
    in this PDF.
    """
    return "undefined" if row == 1 else f"undefined_{row}"


def description_field(row: int) -> str:
    return str(row)


AMOUNT_FIELDS = (
    {amount_field(i) for i in range(1, MAX_LINE_ITEMS + 1)}
    | {TOTAL_FIELD, PAYMENT_BOND_FIELD, PERFORMANCE_BOND_FIELD, GRAND_TOTAL_FIELD}
)


class FillError(Exception):
    """Raised when the payload cannot be filled safely."""


# --------------------------------------------------------------------------
# money handling
# --------------------------------------------------------------------------

def money(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace("$", "").replace(",", "")
    if not text:
        raise FillError(f"empty amount: {value!r}")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise FillError(f"cannot parse amount {value!r}") from exc


def stored_amount(amount: Decimal) -> str:
    """Raw value written to /V, matching what the examples store."""
    if amount == amount.to_integral_value():
        return str(int(amount))
    return f"{amount:.2f}"


def displayed_amount(amount: Decimal) -> str:
    """What AFNumber_Format(2, 0, ...) would render."""
    return f"{amount:,.2f}"


# --------------------------------------------------------------------------
# PDF field helpers
# --------------------------------------------------------------------------

def _inherited(obj, key, depth=8):
    while obj is not None and depth > 0:
        if key in obj:
            return obj[key]
        parent = obj.get("/Parent")
        obj = parent.get_object() if parent is not None else None
        depth -= 1
    return None


def _qualified_name(obj, depth=8) -> str:
    parts = []
    while obj is not None and depth > 0:
        t = obj.get("/T")
        if t:
            parts.insert(0, str(t))
        parent = obj.get("/Parent")
        obj = parent.get_object() if parent is not None else None
        depth -= 1
    return ".".join(parts)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _build_appearance(text: str, width: float, height: float, right_align: bool, font_ref):
    """Recreate the appearance stream Acrobat writes for this form."""
    size = FONT_SIZE
    avail = width - 2 * SIDE_PAD
    text_w = fitz.get_text_length(text, fontname="helv", fontsize=size)
    if text_w > avail > 0:
        # Acrobat shrinks to fit rather than clipping; match that.
        size = max(4.0, size * avail / text_w)
        text_w = fitz.get_text_length(text, fontname="helv", fontsize=size)

    x = (width - text_w - SIDE_PAD) if right_align else SIDE_PAD
    y = height * BASELINE_RATIO

    stream = (
        f"/Tx BMC\nq\nBT\n/Helv {size:.4g} Tf\n0 g\n"
        f"{x:.4g} {y:.4g} Td\n({_pdf_escape(text)}) Tj\nET\nQ\nEMC\n"
    )

    ap = DecodedStreamObject()
    ap.set_data(stream.encode("latin-1"))
    ap[NameObject("/Type")] = NameObject("/XObject")
    ap[NameObject("/Subtype")] = NameObject("/Form")
    ap[NameObject("/FormType")] = FloatObject(1)
    ap[NameObject("/BBox")] = ArrayObject(
        [FloatObject(0), FloatObject(0), FloatObject(width), FloatObject(height)]
    )
    res = DictionaryObject()
    fonts = DictionaryObject()
    fonts[NameObject("/Helv")] = font_ref
    res[NameObject("/Font")] = fonts
    res[NameObject("/ProcSet")] = ArrayObject([NameObject("/PDF"), NameObject("/Text")])
    ap[NameObject("/Resources")] = res
    return ap


# --------------------------------------------------------------------------
# payload -> field values
# --------------------------------------------------------------------------

def load_constants() -> dict:
    return json.loads(CONSTANTS.read_text()) if CONSTANTS.exists() else {}


def build_values(payload: dict) -> tuple[dict, dict, list[str]]:
    """Return (stored_values, display_values, warnings)."""
    warnings: list[str] = []
    constants = load_constants()
    merged = {**constants, **{k: v for k, v in payload.items() if v not in (None, "")}}

    if not merged.get("date"):
        merged["date"] = f"{date.today().month}/{date.today().day}/{date.today().year}"

    stored: dict[str, str] = {}
    for key, field in HEADER_FIELDS.items():
        val = merged.get(key)
        if val in (None, ""):
            warnings.append(f"header field '{key}' is empty")
            continue
        stored[field] = str(val)

    items = payload.get("line_items") or []
    if not items:
        raise FillError("payload has no line_items; refusing to produce a blank form")
    if len(items) > MAX_LINE_ITEMS:
        raise FillError(
            f"{len(items)} line items but the form has only {MAX_LINE_ITEMS} rows. "
            "Consolidate them in the quote before filling."
        )

    subtotal = Decimal("0")
    for idx, item in enumerate(items, start=1):
        desc = str(item.get("description", "")).strip()
        if not desc:
            raise FillError(f"line item {idx} has no description")
        amt = money(item["amount"])
        subtotal += amt
        stored[description_field(idx)] = desc
        stored[amount_field(idx)] = stored_amount(amt)

    declared = payload.get("total_price")
    if declared not in (None, "") and money(declared) != subtotal:
        warnings.append(
            f"quote states total {money(declared)} but line items sum to {subtotal}; "
            "used the line-item sum"
        )

    stored[TOTAL_FIELD] = stored_amount(subtotal)

    grand = subtotal
    for key, field, threshold, label in (
        ("payment_bond", PAYMENT_BOND_FIELD, PAYMENT_BOND_THRESHOLD, "Payment Bond"),
        ("performance_bond", PERFORMANCE_BOND_FIELD, PERFORMANCE_BOND_THRESHOLD,
         "Payment & Performance Bond"),
    ):
        val = payload.get(key)
        if val not in (None, ""):
            amt = money(val)
            stored[field] = stored_amount(amt)
            grand += amt
        elif subtotal > threshold:
            warnings.append(
                f"total {subtotal} exceeds ${threshold:,.0f} and the form asks for a "
                f"{label} cost, but none was provided — left blank"
            )

    stored[GRAND_TOTAL_FIELD] = stored_amount(grand)

    display = {
        k: (displayed_amount(money(v)) if k in AMOUNT_FIELDS else v)
        for k, v in stored.items()
    }
    return stored, display, warnings


# --------------------------------------------------------------------------
# fill
# --------------------------------------------------------------------------

def fill(payload: dict, out_path: Path, sign: bool) -> list[str]:
    if not TEMPLATE.exists():
        raise FillError(f"template missing: {TEMPLATE}")

    stored, display, warnings = build_values(payload)

    writer = PdfWriter(clone_from=PdfReader(TEMPLATE))
    acro = writer._root_object.get("/AcroForm")
    if acro is None:
        raise FillError("template has no AcroForm")
    acro = acro.get_object()
    font_ref = acro["/DR"].get_object()["/Font"].get_object()["/Helv"]
    # We supply appearances ourselves, so viewers must not regenerate them.
    acro[NameObject("/NeedAppearances")] = BooleanObject(False)

    seen = set()
    for page in writer.pages:
        for annot in page.get("/Annots", []):
            obj = annot.get_object()
            name = _qualified_name(obj)
            if name not in stored:
                continue
            seen.add(name)

            target = obj if "/FT" in obj else _inherited(obj, "/FT") and obj
            holder = obj if "/T" in obj else obj["/Parent"].get_object()
            holder[NameObject("/V")] = TextStringObject(stored[name])

            rect = [float(v) for v in obj["/Rect"]]
            width = abs(rect[2] - rect[0])
            height = abs(rect[3] - rect[1])
            right = str(_inherited(obj, "/Q")) == "2"

            ap_stream = _build_appearance(display[name], width, height, right, font_ref)
            ap_dict = DictionaryObject()
            ap_dict[NameObject("/N")] = writer._add_object(ap_stream)
            obj[NameObject("/AP")] = ap_dict

    missing = set(stored) - seen
    if missing:
        raise FillError(f"fields not found in template: {sorted(missing)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        writer.write(fh)

    if sign:
        if not SIGNATURE.exists():
            raise FillError(
                f"signing requested but {SIGNATURE} is missing. "
                "Add a transparent-background PNG of the signature there."
            )
        doc = fitz.open(out_path)
        doc[0].insert_image(SIG_BOX, filename=str(SIGNATURE), keep_proportion=True, overlay=True)
        # A full rewrite rather than saveIncr(): incremental saves append the
        # image uncompressed and balloon the file to several hundred KB.
        buf = doc.tobytes(garbage=3, deflate=True, deflate_images=True)
        doc.close()
        out_path.write_bytes(buf)
    else:
        warnings.append("form left unsigned (--no-sign)")

    return warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("payload", help="path to payload JSON, or '-' for stdin")
    ap.add_argument("-o", "--output", default=None, help="output PDF path")
    ap.add_argument("--no-sign", action="store_true", help="leave the signature line blank")
    args = ap.parse_args(argv)

    raw = sys.stdin.read() if args.payload == "-" else Path(args.payload).read_text()
    payload = json.loads(raw)

    if args.output:
        out = Path(args.output)
    else:
        campus = str(payload.get("campus_name", "quote")).replace(" ", "-")
        out = ROOT / "output" / f"SAISD-RFQ-{campus}-{date.today():%Y%m%d}.pdf"

    try:
        warnings = fill(payload, out, sign=not args.no_sign)
    except FillError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {out}")
    for w in warnings:
        print(f"  WARNING: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
