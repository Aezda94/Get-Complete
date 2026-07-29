# Get-Complete — SAISD quote form automation

San Antonio ISD requires a "Request for Quote" form alongside every quote we
submit. This turns a Get Complete estimate into that form — filled, totalled
and signed — in one command.

> **This repo is currently PUBLIC.** The signature, the estimates and the
> completed forms are deliberately excluded by `.gitignore`, which means a
> fresh clone cannot actually run the tool. Switch the repo to private
> (Settings → Danger Zone → Change visibility), then relax `.gitignore` so
> `form-template/` and `assets/signature.png` travel with the code.

## Use it

```bash
.venv/bin/python scripts/make_form.py path/to/estimate.pdf
```

Output lands in `output/SAISD-RFQ-<campus>-<date>.pdf`. Read the warnings it
prints before sending anything.

| Flag | Effect |
| --- | --- |
| `--no-sign` | Draft for review, signature line left blank |
| `--form-date 7/22/2026` | Override the form date (defaults to today) |
| `--show-payload` | Print extracted values before filling |
| `-o path.pdf` | Choose the output path |

Or ask Claude — the `quote-form` skill in `.claude/skills/` runs the same
pipeline and reports the warnings back.

## How it works

```
estimate.pdf ──▶ extract_quote.py ──▶ payload.json ──▶ fill_form.py ──▶ signed form
```

Splitting extraction from filling means a redesigned estimate template breaks
loudly at step one instead of quietly mis-filling the form.

Both steps are deterministic. Verified by regenerating both known examples and
diffing: all 41 form fields match, and the rendered page is pixel-identical
apart from sub-pixel antialiasing.

## Layout

| Path | What belongs here |
| --- | --- |
| `scripts/` | The pipeline. `make_form.py` is the entry point. |
| `form-template/` | Blank SAISD form, unsigned. Not committed while public. |
| `assets/constants.json` | Company name, rep, email, phone. |
| `assets/signature.png` | Transparent-background signature. Never committed. |
| `examples/quotes/` | Source estimates. Not committed. |
| `examples/completed-forms/` | Hand-filled forms used to derive the mapping. |
| `output/` | Generated forms. Not committed. |
| `.claude/skills/quote-form/` | Skill definition and `references/field-map.md`. |

## Setup on a new machine

```bash
python3 -m venv .venv
.venv/bin/pip install pymupdf pypdf pdfplumber pillow
```

## Gotchas worth knowing

- **Amounts come from the estimate's TOTAL column, not PRICE.** PRICE is a
  unit rate.
- **Repeated line items are never merged.** Two `Plumbing Labor` rows means
  two techs assigned; merging them loses that.
- **The form stores raw numbers but displays formatted ones** (`1140` →
  `1,140.00`). `fill_form.py` writes both, so it prints correctly in viewers
  that don't run JavaScript. See `references/field-map.md`.
- **The bond lines are never auto-filled.** The script warns when a total
  crosses $25,000 or $100,000 so the omission is a decision, not an oversight.
