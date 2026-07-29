# Field map — SAISD Request for Quote

Derived by diffing two estimate/form pairs:

- `LBE2.pdf` — Luther Burbank High School, quote 88135518
- `JBE.pdf` → `JBQF.pdf` — James Bonham Academy, quote 87955663

Both reproduce byte-identically from `scripts/make_form.py`, so the rules
below are verified, not assumed.

## Header

| Form field (PDF name) | Source in the estimate | Notes |
| --- | --- | --- |
| `Date` | **not** the quote date | Date the form is submitted. Bonham's quote was 7/21, the form 7/22. Defaults to today. |
| `Campus Name` | first line of the **JOB ADDRESS** block | The site, not the district: "James Bonham Academy", not "San Antonio ISD". |
| `BidContract Number` | the **QUOTE** number | 8 digits in both examples. |
| `Company Name` | constant | `Get Complete Maintenance and Repair`. Has changed before — it lives in `assets/constants.json`. |
| `Company Representative Name` | constant | Amanda Hernandez |
| `Company Representative email` | constant | service@getcompletetx.com |
| `Company Representative Phone` | constant | (737) 312-7905 |

The BILL TO block (San Antonio ISD) is never used on the form.

## Line items

Rows 1–15. Field names are inconsistent in the source PDF and must not be
inferred from field order — they were confirmed against widget geometry:

| Row | Description field | Amount field |
| --- | --- | --- |
| 1 | `1` | `undefined` |
| 2–15 | `2` … `15` | `undefined_2` … `undefined_15` |

Rules:

- Description comes from the estimate's **DESCRIPTION** column with the
  surrounding asterisks stripped: `*Dispatch Fee*` → `Dispatch Fee`.
- Amount comes from the **TOTAL** column, never **PRICE**. PRICE is a unit
  rate; 4 hrs × $130.00 lands on the form as `520`.
- **Repeated rows are never merged.** Two `Plumbing Labor` rows at 8 hours
  each means two techs assigned. Collapsing them into one 16-hour row would
  destroy the crew-size information. This is deliberate — do not "tidy" it.
- More than 15 items will not fit; the script refuses rather than truncating.

## Totals

| Form field | Rule |
| --- | --- |
| `Total Price` | Sum of the line items, computed here rather than copied. A mismatch against the estimate's QUOTE TOTAL is reported as a warning. |
| `undefined_16` | Payment Bond cost. Blank unless supplied. |
| `undefined_17` | Payment & Performance Bond cost. Blank unless supplied. |
| `Grand Total Price` | Total + both bond lines. |

The form asks for a Payment Bond over $25,000 and a Payment & Performance
Bond over $100,000. Both examples left these blank, including Luther Burbank
at $67,500 — which is over the first threshold. The script warns when a total
crosses either line so the omission is at least deliberate.

## Number formatting — the non-obvious part

Amount fields carry `AFNumber_Format(2, 0, 0, 0, "", true)` and `/Q 2`, so
Acrobat **stores a raw value but displays a formatted one**:

| Stored in `/V` | Displayed |
| --- | --- |
| `1140` | `1,140.00` |
| `100` | `100.00` |

`scripts/fill_form.py` writes both: the raw value to `/V`, and a hand-built
appearance stream showing the formatted, right-aligned text. That second half
matters — viewers that don't run JavaScript (Preview, Chrome, most print
paths) show only the appearance stream, so without it the form would print
left-aligned `1140`.

Typography copied from Acrobat's own output: `/Helv 8.118 Tf`, baseline at
`0.2676 × box height`, 2pt side padding, right-aligned at
`box width − text width − 2`. Verified to within 0.02pt.

Text fields are left-aligned with no formatting script.

## Signature

Both completed forms embed the same signature image (identical SHA-1) as a
black JPEG plus an alpha mask. It was extracted, composited, trimmed, and
saved to `assets/signature.png` with a transparent background.

Placement differs slightly between the examples (x 394.8 vs 382.4), so there
is no strict convention. The script fits it proportionally into
`(392.0, 128.9) – (544.2, 174.8)`, which centres it on the ruled line.

## Left blank

The `SAISD Acceptance of Scope of Work` block — Date, Name, Signature — is
for SAISD to complete. Never fill it.
