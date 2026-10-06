# 0047 — A specialty is a reference pack the clinic enables, edits and can restore

- **Status:** accepted
- **Date:** 2026-10-04
- **Deciders:** Eduardo
- **Tags:** catalog, treatments, apps

## Context

The catalogue recognised seventeen dental disciplines. Ten came with
treatments, seeded into every clinic whether it practised them or not;
seven were offered with nothing behind them, which is worse than not
offering them. A clinic had no way to say "we do not do orthodontics" short
of retiring treatments one by one, and no way back to the starting point
after editing.

The request was for each speciality to be like an App — Orthodontics with
its whole catalogue and its plan templates — switched on and off from the
Treatments settings, customisable, and restorable with a warning.

## Decision

**Each recognised discipline is a *pack*: a reference catalogue of
treatments and plan templates, held in code. A clinic enables the packs it
practises, owns the copy it gets, and can restore a pack to the reference.**

1. **A pack is not an App.** Apps (`backend/apps.json`, ADR 0036) group
   *modules* and switch *code* for a whole deployment. A pack is *data*,
   switched per clinic, inside one App — Treatments. It is configured from
   that App's settings page.
2. **The reference is code, the catalogue is the clinic's.** Enabling
   copies reference treatments into the clinic's catalogue. From then on
   they are ordinary rows the clinic edits. The reference is never read at
   run time to price or draw anything.
3. **Enable never overwrites.** It adds what the clinic lacks and brings
   back what disabling switched off. It is also how a clinic gets
   treatments added to the reference later.
4. **Disable deletes nothing.** Plans, budgets and the chart point at
   catalogue rows. The pack's reference treatments that no other enabled
   discipline claims are deactivated and marked (`disabled_by_specialty`),
   so enabling again restores exactly those — not the ones the clinic
   retired by hand, and never a treatment the clinic created.
5. **Restore overwrites, and says so.** Every reference treatment of the
   pack goes back to the reference; what the clinic changed on them is
   lost, what the clinic added is kept. The API reports how many are
   customised so the screen can warn with a number before doing it.
6. **A pack's treatment belongs to that pack.** Pack items name their
   discipline outright; they do not inherit one from the browsing
   category. Otherwise every radiograph would be "general dentistry" and
   no clinic could be without it.
7. **Plan templates follow by event.** The catalogue owns treatments; the
   treatment-plan module owns templates. The catalogue announces
   `catalog.specialty_enabled / _disabled / _restored` and that module
   reacts (ADR 0042: events write).

## Consequences

### Good

- A clinic's catalogue holds what it practises. New clinics start with
  the ten baseline packs instead of everything.
- Every discipline offered has something behind it.
- "Start again" exists, per discipline, with its cost stated.
- The reference can grow: a clinic sees *N new* and adds them without
  losing its edits.

### Bad / accepted trade-offs

- **The content is a first reference, not a reviewed standard.** 706
  treatments written to be edited; prices are placeholders on the seed's
  scale. A clinic adopting a pack is expected to review it.
- **Per clinic, not per doctor.** One catalogue per clinic. Two doctors
  with different fees for the same treatment is not modelled.
- A treatment two packs share stays while either is enabled; restoring one
  pack resets it for both.
- Restore is all-or-nothing per pack. There is no per-treatment restore.
- A pack that is disabled cannot be restored; it has to be enabled first.

## Alternatives considered

- **One App per speciality in `apps.json`.** Rejected: per-deployment, a
  restart to change, and no code to switch — only data.
- **Read the reference at run time (no copy).** Rejected: a clinic could
  not rename or reprice anything, and a change to the reference would
  silently change every clinic's catalogue.
- **Delete on disable.** Rejected: catalogue rows are referenced by plans
  and budgets.
- **Reuse `is_active` alone for disable.** Rejected: re-enabling could not
  tell what the pack switched off from what the clinic retired.

## How to verify the rule still holds

`backend/tests/test_specialty_packs.py`: every discipline has a
catalogue; a clinic starts with the baseline only; enabling leaves the
clinic's own alone; disabling deletes nothing and enabling brings exactly
that back; a shared treatment stays while one discipline is on; restoring
overwrites the reference and keeps what the clinic added; a reference that
grew is added without touching the rest.
