---
name: quote-form
description: Fill out the customer's mandatory quote submission form from one of our quotes, and sign it. Use whenever the user provides a quote (PDF, Word, Excel, or pasted text) and asks for the customer form, the submission form, the quote form, or says they are submitting a quote to this customer. Also use for questions about how a field on that form should be filled.
---

# Customer quote submission form

Translates one of our quotes into the customer's required submission form.
The form is rigid and cannot be changed — reproduce it exactly.

> **STATUS: NOT YET BUILT.** The field map and filler script are pending
> example quotes and completed forms. Until those exist, do not guess at
> the mapping — tell the user what is missing instead.

## Inputs

- The quote: `examples/quotes/` holds past ones; the user supplies a new one.
- The blank form: `form-template/`
- Signature: `assets/signature.png` (transparent background)
- Field mapping rules: `references/field-map.md`

## Procedure

1. Read `references/field-map.md` in full before touching the form.
2. Extract every source value from the quote. Do not infer values that the
   quote does not state — carry them from `references/constants.md` when they
   are company constants, and otherwise flag them.
3. Run `scripts/fill_form.py` to write the filled form. Fill
   programmatically; never rebuild the document by hand, because the
   customer's layout must survive byte-for-byte where possible.
4. Stamp the signature and the submission date.
5. Write to `output/` and report a short list of: fields filled, fields
   carried from constants, and anything that needed a judgment call.

## Rules

- Never invent a price, lead time, part number, or term. If the quote does
  not state it, flag it and stop rather than filling a plausible value.
- Signature goes on only after every other field is filled and checked.
- Match the customer's formatting conventions exactly — date format, currency
  symbols, decimal places, uppercase fields. These are recorded in the field
  map and derived from the completed examples, not assumed.
