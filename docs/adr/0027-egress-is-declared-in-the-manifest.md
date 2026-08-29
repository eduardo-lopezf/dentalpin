# 0027 — Egress is declared in the manifest, and reported before it is blocked

- **Status:** accepted
- **Date:** 2026-08-29
- **Deciders:** Eduardo
- **Tags:** privacy, modules, compliance

## Context

`PrivacyPolicy.egress_allowed` has been default-deny since ADR 0023 and
has had **nothing to compare against**. The policy could say a tenant may
reach OpenAI; nothing in the codebase said which modules reach anything
at all.

That answer lived in three places at once — the provider factory in
`copilot`, an HTTP client in `whatsapp_kapso`, a SOAP client in
`verifactu` — and, separately, in whatever a clinic's data-processing
agreement happened to list. A register maintained by hand is correct on
the day it is written and wrong the next time somebody adds a module.

Writing this down surfaced a fourth destination nobody had counted:
`notifications` sends patient reminders through **whatever SMTP server
the clinic configures**. It is egress by any definition — a name and an
email address leaving the deployment — and it was invisible precisely
because the receiving party is configuration rather than a vendor named
in code.

## Decision

**A module declares where it sends data, in its manifest, next to
everything else it declares.**

```python
manifest = {
    "egress": [
        {
            "target": "openai",
            "subprocessor": "OpenAI, L.L.C.",
            "residency": "us",
            "data_classes": ["identifier", "clinical", "operational"],
            "purpose": "Generar las respuestas del copiloto. …",
            "required": False,
        }
    ],
}
```

Four things follow.

1. **`target` is an id, `subprocessor` is a legal name.** The first is
   matched against `TENANT_EGRESS_ALLOWED`, so it must be typeable
   without guessing at casing. The second goes into a contract, so
   `"OpenAI"` is not enough and the parser rejects an empty one.
   `purpose` is prose a clinic can show a patient.

2. **`data_classes` reuses ADR 0025's axis**, so a declaration says
   *what kind* of data leaves, not merely that something does. An empty
   set means the module calls out without sending anything personal — a
   licence check — and the boot audit grades it differently for exactly
   that reason.

3. **The subprocessor register is generated, not remembered.**
   `docs/subprocessors-catalog.md` is produced by
   `generate_catalogs.py` alongside the module and event catalogs, and
   CI fails on drift. The document a clinic attaches to its DPA now
   cannot disagree with the code.

4. **The declaration is about where the data goes, not which file
   dials.** `copilot` reaches OpenAI through `app/core/llm/` and
   `notifications` sends mail through `app/core/email/`; both declare it
   anyway, because a patient asking who receives their data is not asking
   about the call graph.

### Reported, not blocked — and why

`egress_allowed` is default-deny, and **no deployment has declared
anything yet**. Enforcing the field today would silently unplug the
copilot, stop appointment reminders, and halt Verifactu submissions on
every existing install — breaking working clinics to enforce a field
nobody has had a release to fill in.

So the audit runs at boot and **warns**, naming each module, its
destination, its subprocessor, and what class of data it carries. The
finding is the product for this step. Blocking becomes reasonable once
operators have declared, and turning it on is then a change to one
function rather than a redesign.

The `required` flag exists for that day: a destination a module can work
without (`copilot`'s OpenAI) can be refused without unmounting the
module, while a required one (`verifactu`'s AEAT) cannot.

## Consequences

### Good

- `PrivacyPolicy.egress_allowed` stops being a field with no referent —
  it now has something concrete to permit or not.
- The DPA register is a build artifact. Adding a vendor call without
  updating it is a CI failure rather than a paperwork oversight.
- A test fails when a module imports an HTTP or SMTP client without
  declaring egress, which is the case this exists to catch: a module
  quietly acquiring a vendor and nobody noticing.
- The SMTP destination is now visible. It was the easiest to miss and it
  carries a patient's name and address on every reminder.

### Bad / accepted trade-offs

- **Nothing is blocked.** A module can still call a destination the
  policy forbids; the deployment merely says so at boot. Until an
  operator sets `TENANT_EGRESS_ALLOWED`, every boot logs four warnings,
  which risks becoming noise people learn to skip.
- **The declaration is a claim, not a measurement.** Nothing verifies
  that a module's declared destinations are the ones it actually
  contacts, or that the declared `data_classes` match what is in the
  payload. The client-import test raises the floor; it does not prove
  the ceiling.
- `residency` is free text and mostly `"unspecified"`, because the
  vendors do not commit to a region in a form we can assert.
- The `notifications` subprocessor is a sentence rather than a name,
  because the receiving party is whatever the clinic configured. That is
  honest, and it is also unusable as a contract line — the clinic has to
  fill it in.

## Alternatives considered

- **Detect egress by scanning source for HTTP clients** — that is the
  *test*, not the source of truth: it can tell you a module dials
  something, never who receives it, why, or what class of data goes.
- **Keep the register in `docs/` by hand** — the failure mode this
  replaces. It was right once.
- **Block on day one** — unplugs the copilot and reminders on every
  existing deployment to enforce an unset field. The safe order is
  declare, observe, then enforce.
- **Put the destinations in `PrivacyPolicy`** — wrong direction. The
  policy says what a *tenant* permits; the manifest says what a *module*
  does. Merging them would mean editing core to add a module.

## How to verify the rule still holds

- `backend/tests/test_egress_declarations.py` — declaration parsing and
  its refusals, the audit against a default-deny policy, and
  `test_modules_making_outbound_calls_declare_egress`, which fails when a
  module imports `httpx`/`smtplib`/… without declaring.
- `python backend/scripts/generate_catalogs.py --check` fails when
  `docs/subprocessors-catalog.md` drifts from the manifests.

## References

- `backend/app/core/privacy/egress.py`
- `backend/app/core/plugins/manifest.py` — `Manifest.egress`
- `docs/subprocessors-catalog.md` — the generated register
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — `egress_allowed`
- [ADR 0025](0025-pii-is-classified-on-the-column.md) — the `DataClass` axis
