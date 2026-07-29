---
name: quote-form
description: Fill out and sign the SAISD Request for Quote form from a Get Complete estimate. Use whenever the user provides an estimate or quote PDF and asks for the SAISD form, the customer form, the submission form, the quote form, or says they are submitting a quote to SAISD or San Antonio ISD. Also use for questions about how a field on that form should be filled.
---

# SAISD Request for Quote

San Antonio ISD requires this form alongside every quote. The form is rigid
and cannot be changed. The whole job is one command.

## Do this

```bash
.venv/bin/python scripts/make_form.py path/to/estimate.pdf
```

Then **report the summary it prints and every warning verbatim**, and give the
user the output path. Warnings are the point — they mark the places where the
estimate was ambiguous or a threshold was crossed.

Useful flags:

- `--form-date 7/22/2026` — the form date defaults to today, which is what
  SAISD expects. Override only if backdating to match a submission.
- `--no-sign` — a draft to review before signing.
- `--show-payload` — print the extracted values first, for spot-checking.
- `-o path.pdf` — output location. Defaults to
  `output/SAISD-RFQ-<campus>-<today>.pdf`.

## When the estimate does not parse

`scripts/extract_quote.py` locates values by column geometry, so a redesigned
estimate template will make it fail loudly rather than silently mis-fill.
If that happens:

1. Run `scripts/extract_quote.py estimate.pdf` alone to see how far it gets.
2. Read `references/field-map.md` before touching anything.
3. Fix the extractor, or hand-write the payload JSON and call
   `scripts/fill_form.py payload.json`. Do not fill the PDF by any other
   route — the number formatting is easy to get wrong in a way that looks
   fine on screen and prints wrong.

## Rules

- **Never invent a price, quantity, campus, or quote number.** If the estimate
  does not state it, say so and stop. A wrong number on a form that
  accompanies an invoice is worse than a delayed form.
- **Never merge repeated line items.** Two `Plumbing Labor` rows means two
  techs. Merging destroys crew-size information the scheduler depends on.
- **Amounts come from the TOTAL column, not PRICE.** PRICE is a unit rate.
- **Leave the SAISD Acceptance block empty.** Date, Name and Signature there
  belong to SAISD.
- The signature is stamped automatically from `assets/signature.png`. It is
  Amanda Hernandez's real signature — only sign forms she has asked for.

## Layout

| Path | What it is |
| --- | --- |
| `scripts/make_form.py` | Estimate PDF in, signed form out. Start here. |
| `scripts/extract_quote.py` | Estimate PDF → payload JSON. |
| `scripts/fill_form.py` | Payload JSON → filled, signed PDF. |
| `form-template/SAISD-Quote-Form-fillable.pdf` | Blank form, unsigned. |
| `assets/constants.json` | Company name, rep, email, phone. |
| `assets/signature.png` | Transparent-background signature. |
| `references/field-map.md` | Every mapping rule and why. |
