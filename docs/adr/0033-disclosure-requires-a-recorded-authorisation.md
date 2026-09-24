# 0033 — Disclosure requires a recorded authorisation, and the authorisation is part of the record

- **Status:** proposed
- **Date:** 2026-09-22
- **Deciders:** Eduardo
- **Tags:** clinical, privacy, compliance, security

## Context

A dentist refers a patient to an endodontist and sends the relevant part
of the chart. A hospital asks for a surgical history. An insurer asks for
proof of a procedure. A patient asks for their own record. These look
like one feature — "share the record" — and they are four different legal
acts with four different requirements.

[ADR 0027](0027-egress-is-declared-in-the-manifest.md) already made the
*route* explicit: a module that talks to an external service declares the
target, the subprocessor, the purpose and the data classes it sends. That
is a statement about the software's shape, made once, at build time. It
answers "can this module send data there at all?" It cannot answer
"did *this patient* agree to *this disclosure*, of *this scope*, to
*this recipient*?" — which is a runtime fact about one person, and the
question a clinic is actually asked when challenged.

Health data is special category under RGPD Art. 9 and *datos sensibles*
under Mexico's LFPDPPP, which generally requires express written consent
to transfer it — subject to exceptions that include transfers necessary
for medical diagnosis and the provision of healthcare. NOM-004-SSA3-2012
additionally requires that consent letters form part of the *expediente*
itself, not a separate filing cabinet. The exact obligations are for
local counsel; what is architectural is that the answer varies by
*purpose*, and that the evidence has to live somewhere retrievable.

The naive model — a `shared: true` flag, or a signature demanded before
every send — fails in both directions. It loses scope, recipient, expiry
and revocation, none of which are booleans. And demanding a signed form
for an ordinary same-care referral builds friction that clinics route
around: they attach a PDF to a personal email instead, which is worse for
the patient than the thing the friction was protecting them from.

## Decision

**No clinical data leaves the clinic without a `Disclosure` that names
the recipient, the purpose, the scope and the legal basis — and the
disclosure, with its authorisation evidence and a manifest of what was
actually sent, is itself an entry in the patient's record.**

Six clarifications:

1. **Purpose selects the basis; the basis selects the evidence.** The
   product does not ask the clinic to pick a legal basis — it asks *why*,
   in clinical language, and derives the rest from the tenant's
   `PrivacyPolicy.jurisdictions` ([ADR 0023](0023-privacy-policy-and-custody-modes.md)).

   | Purpose | Typical basis | Evidence required |
   |---|---|---|
   | Continuity of care (referral, interconsultation) | Provision of healthcare by a professional bound by secrecy | Recorded clinical justification + named recipient |
   | Patient's own copy | Subject access — the patient is the subject | Identity verification |
   | Second opinion at the patient's request | Patient's express instruction | Express authorisation |
   | Insurer, employer, third-party administrator | Express consent | Signed authorisation, scoped and time-boxed |
   | Legal or judicial requirement | Legal obligation | The order itself, filed with the disclosure |
   | Research, teaching, statistics | Consent, or anonymisation instead | Express authorisation, or proof the payload carries no identifiers |

   The common case — a referral for the patient's own treatment — stays
   one interaction. The unusual case is rigorous. Making that split is
   the whole point; a uniform rule would get one of the two wrong.

2. **Scope is enforced, not advisory.** A disclosure names the sections,
   date range or documents it covers, and the export honours it. This is
   an invariant with a chokepoint in the sense of
   [ADR 0029](0029-security-invariants-with-chokepoints.md): there is one
   place clinical payloads are assembled, it takes a `Disclosure`, and
   there is no path around it. A caller that wants to send something
   outside the consented scope gets a refusal, not a warning.

3. **The disclosure records what was sent, not only what was allowed.**
   Permission and payload drift apart — the record grows between the
   authorisation and the send. Each disclosure stores a manifest of the
   entries actually included and a digest of the produced document, using
   the chaining `verifactu` already applies to fiscal records. "What
   exactly did they receive, and can you prove it?" is answerable without
   regenerating anything, which regeneration would not honestly answer.

4. **Revocation is append-only, and the product states its real effect.**
   A revocation is a new entry, never a deletion of the original grant.
   It stops future disclosure under that authorisation and it cannot
   recall what already left. The UI says that in those words. Implying
   recall would be the more comfortable lie and the one that damages a
   patient who relied on it.

5. **The authoriser is not always the patient.** Minors and patients
   under guardianship authorise through a legal representative;
   `patients_clinical_legal_guardian` already models who that is. The
   disclosure names the authoriser and the capacity they acted in, and a
   capacity that has since lapsed does not retroactively invalidate a
   disclosure made while it held.

6. **Custody mode changes who is involved, not whether the rule binds.**
   Under `MANAGED` or `BYOK` a disclosure leaving through our
   infrastructure involves a declared subprocessor. Under `SELF`
   ([ADR 0028](0028-self-hosting-is-the-premium-tier.md)) it does not
   traverse anything we operate and there is no subprocessor to name —
   the `Disclosure` is still required, because it is the clinic's
   evidence, not ours.

## Consequences

### Good

- The clinic can answer the three questions it is actually asked — who
  received it, what exactly, and on whose authority — from the patient's
  own record.
- The consent letter lands where NOM-004 expects it: inside the
  *expediente*, visible in the timeline next to the act it authorised.
- Ordinary referrals stay fast, so the secure path stays the convenient
  one and personal email stops being the workaround.
- Subject access requests ([ADR 0026](0026-subject-rights-are-a-module-contract.md))
  and clinical disclosures converge on one audit surface instead of two.

### Bad / accepted trade-offs

- A new concept for clinics to learn, and a screen they must fill before
  a send that used to be a click. Mitigated by deriving everything
  derivable and defaulting the continuity-of-care case.
- The purpose→basis table is jurisdiction-specific and will be wrong
  somewhere. It is data read from the tenant policy, not logic, so a new
  jurisdiction is a row rather than a release — but the first version of
  each row needs local review.
- Storing a manifest and digest per disclosure grows with sharing volume.
- A disclosure that was legitimate under a basis the clinic later
  disputes cannot be retracted from the record. That is the intent.

## Alternatives considered

- **A boolean consent flag on the patient.** Loses recipient, scope,
  purpose, expiry and revocation — every field that distinguishes a
  lawful disclosure from an unlawful one. It also makes one blanket
  agreement authorise every future send, which is precisely what express
  consent is defined to exclude.
- **Consent as a `media` attachment only.** The signed PDF is evidence,
  but a document in a folder cannot be queried by the chokepoint, cannot
  express scope, and cannot be revoked. The artifact is stored, but the
  authorisation is structured.
- **Reusing `manifest.egress` alone.** Necessary and not sufficient — it
  describes routes, not per-patient permission. Both apply: egress says
  the channel is declared, disclosure says this payload may use it.
- **Demanding a signature for every disclosure including referrals.**
  Rejected in clarification 1: it drives clinics off-platform, and the
  net privacy outcome is worse.
- **A separate consent module.** A disclosure is meaningless without the
  record it discloses, and the chokepoint must sit where payloads are
  assembled. It belongs with the record, not beside it.

## How to verify the rule still holds

- A chokepoint test: every clinical export path requires a `Disclosure`,
  and a payload assembled outside the consented scope raises rather than
  truncates. Modelled on the existing
  `tests/test_event_transaction_boundary.py` allowlist — new bypasses
  fail the suite instead of passing silently.
- A revocation test: after revoking, a new disclosure under the same
  authorisation is refused, while the original disclosure's manifest and
  digest remain retrievable.
- A scope test: a disclosure limited to a section or date range produces
  a document containing exactly that, asserted against the manifest.

## References

- [ADR 0027](0027-egress-is-declared-in-the-manifest.md) — declared routes
- [ADR 0026](0026-subject-rights-are-a-module-contract.md) — subject rights
- [ADR 0023](0023-privacy-policy-and-custody-modes.md) — `PrivacyPolicy.jurisdictions`
- [ADR 0029](0029-security-invariants-with-chokepoints.md) — invariants with chokepoints
- [ADR 0006](0006-budget-public-link-2-factor-auth.md) — the expiring-link + 2FA pattern reused for remote authorisation
- `backend/app/modules/patients_clinical/models.py` — `patients_clinical_legal_guardian`
- `docs/features/expediente-clinico.md` §5 — the authorisation flows
- RGPD Art. 9; LFPDPPP (MX); NOM-004-SSA3-2012 — to be confirmed with local counsel
