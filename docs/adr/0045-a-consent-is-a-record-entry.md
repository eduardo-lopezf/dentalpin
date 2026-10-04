# 0045 — A consent is a record entry, written from the clinic's own text

- **Status:** accepted
- **Date:** 2026-10-03
- **Deciders:** Eduardo (product owner)
- **Tags:** clinical, compliance, privacy, apps

## Context

Two obligations had nothing behind them. NOM-004-SSA3-2012 expects the
*cartas de consentimiento informado* to be in the clinical record, and
Ley General de Salud Art. 51 Bis 1 gives the patient a right to clear
information about a procedure, its risks and its alternatives — a duty on
the clinical act. Separately, the data-protection regime expects consent
to the processing of health data against a privacy notice, and the
product recorded none
([commitments register](../technical/commitments-register.md), 2, 4 and
21). The nearest artifact, a signed budget, proves a price was accepted
and nothing else.

The question was where this lives — a new App, an add-on, or a module —
and what a consent *is* in the data model.

## Decision

**Consents are a module, `consents`, of the Clinical record App. A
consent is an entry of the clinical record, written from a text the
clinic owns.**

- **One module, two kinds.** `informed` (to treat) and `data_use`
  (processing of personal data) share the mechanism — a text, a
  signature, a revocation — and nothing of the meaning. Neither replaces
  the other, and a signed budget replaces neither.
- **Append-only** ([ADR 0032](0032-clinical-record-is-append-only.md)).
  Only a draft is edited. A signed, declined or revoked consent is never
  edited or deleted; revoking adds a state and a date and keeps the text
  and the signature. There is no delete endpoint.
- **The letter holds its own text.** It is written from a template and
  stores a copy plus the template's version, so rewording a template
  never changes what somebody signed, and "which privacy notice did they
  accept" has an answer.
- **An informed consent names who explained it.** It cannot be signed
  otherwise. The professional is kept as a snapshot — id, name, licence —
  read through `ProfessionalDirectory`, with no foreign key
  ([ADR 0039](0039-modules-reach-each-other-through-core-contracts.md),
  [ADR 0042](0042-core-apps-must-stay-separable.md)).
- **No legal wording ships.** Templates are the clinic's and its
  counsel's. The module supplies the mechanism and the custody.
- **Scope of NOM-004 content:** the dental record, plus family history
  and prognosis, which are cheap and useful in dentistry. The systems
  review and laboratory results of a general medical history are out.

## Consequences

### Good

- The record can show that a patient was informed, by whom, and what they
  signed — and that survives the professional leaving, the template
  changing and the patient withdrawing.
- Consents appear in the composed record
  ([ADR 0034](0034-the-record-is-composed-not-stored.md)) with no new
  plumbing: the module contributes a section.
- The same module closes the data-consent gap before WhatsApp messaging
  makes it wider.

### Bad / accepted trade-offs

- **Mechanism, not compliance.** Nothing here makes a clinic compliant by
  itself: the texts are theirs, nothing forces a consent before a
  procedure or before messaging a patient, and the reading of both norms
  is an engineering one, pending legal review.
- **With Professionals off, informed consents cannot be signed.** That
  App is optional today; a clinic that wants this needs it on.
- The signature is an image on the row, or — for a letter printed and
  signed by hand — the scan filed among the patient's documents, which the
  consent points at by id. No second factor, no remote signing yet.

## Alternatives considered

- **A separate App** — it would depend on Patients and Clinical record
  for no gain: a consent is part of the record, not a neighbour of it.
- **An add-on per jurisdiction** — the mechanism is the same everywhere;
  what varies by country is the text, which is a template.
- **Reuse `budget_signatures`** — a commercial acceptance presented as
  proof that risks were explained is the document a clinic cannot defend.

## How to verify the rule still holds

- `backend/tests/modules/consents/test_consents.py` — a signed consent is
  not edited or discarded, only revoked; an informed consent is not signed
  without a professional; the letter keeps its text when the template
  changes; signed letters are in the record.
- `frontend/tests/e2e/consents.spec.ts` — the same, through the screen.

## References

- `backend/app/modules/consents/`
- `docs/features/expediente-clinico.md` §5 *Two consents, not one*, §9
