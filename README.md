# Get-Complete — customer quote form automation

Automates the rigid form that one customer requires alongside every quote we
submit. Give Claude a quote, get back the customer's form, filled and signed.

> **This repo is currently PUBLIC.** Do not add signatures, real quotes, or
> customer pricing until it is switched to private. `.gitignore` blocks those
> paths as a safety net, but the right fix is repo settings → Danger Zone →
> Change visibility → Private.

## Where things go

| Path | What belongs here |
| --- | --- |
| `form-template/` | The blank customer form, exactly as they send it. One file. |
| `examples/quotes/` | Real quotes we've submitted. |
| `examples/completed-forms/` | The filled form that went with each quote. |
| `assets/` | Signature image (transparent PNG), company constants. |
| `scripts/` | The deterministic filler script. |
| `output/` | Generated forms. Not committed. |
| `.claude/skills/quote-form/` | The skill Claude loads to do the work. |

Name matched pairs the same so the mapping is unambiguous, e.g.
`examples/quotes/Q-10432.pdf` ↔ `examples/completed-forms/Q-10432-form.pdf`.
Three to five pairs is plenty; more only helps if they cover edge cases
(multi-line-item quotes, freight, alternates, no-bid).

## How it will work once built

Drop a quote in and ask for the form. The skill:

1. Extracts the fields from the quote.
2. Maps them to the customer's form per `references/field-map.md`.
3. Fills the form template — deterministically, via script, not by
   re-typesetting the document.
4. Stamps the signature and date.
5. Writes the result to `output/` and flags anything it had to guess.

## Status

Scaffolding only. The field map and filler script get built once the example
quotes and completed forms are in place.
