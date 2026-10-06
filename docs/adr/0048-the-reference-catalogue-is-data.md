# 0048 — The reference catalogue is data: one file per specialty, every treatment explicit

- **Status:** accepted
- **Date:** 2026-10-04
- **Deciders:** Eduardo
- **Tags:** catalog, treatments, data

## Context

The reference catalogue of [ADR 0047](0047-a-specialty-is-a-reference-pack.md)
— 260 treatments across seventeen disciplines — lived in Python: one
literal of more than two thousand lines, plus tables of prefix rules that
decided, from the shape of a code, which disciplines a treatment belonged
to (`REST-CROWN-` → also Rehabilitation) and which stage of care it fell
under (`ORTO-RET-` → maintenance).

Two problems. The people who can say whether a list of orthodontic
treatments is right are orthodontists, and they cannot review a Python
module. And half of what the catalogue said about a treatment was not on
the treatment: it was in a rule elsewhere, invisible to anyone reading the
list and easy to break by naming a new code.

## Decision

**The reference catalogue is data: `catalog/reference/<specialty>.json`,
one file per discipline, in which every treatment says everything about
itself. The files are validated when the application starts.**

1. **One file per discipline**, holding its name, its sub-areas and its
   treatments. Adding a discipline is adding a file (and its key to
   `reference.SPECIALTY_ORDER`).
2. **Nothing is derived from a code.** Each treatment carries its
   `category`, its `specialties`, its `phase` and its `subarea`. The
   prefix tables are gone.
3. **A treatment is written once**, in the file of the discipline it
   belongs to first, and names every discipline that claims it. No
   duplication to drift.
4. **Sub-areas are part of the reference**, not of the clinic's
   catalogue: metadata resolved by code, so every clinic gets them without
   a migration and a clinic's own treatments simply have none.
5. **Validated on import** (`reference.py`, strict Pydantic): unknown
   fields, repeated codes, unknown disciplines, categories or sub-areas
   stop the start. A catalogue that is quietly wrong is worse than an
   application that refuses to boot.
6. **Codes are identity.** A clinic recognises a treatment it already has
   by its code. A code is never renamed or reused.

The move changed nothing for a clinic: the catalogue read from the files
was compared against the Python one — 260 treatments, no difference in any
field, discipline or phase — before the Python data was removed.

## Consequences

### Good

- A specialist can review and correct a discipline's file.
- A change to the catalogue is a diff of the catalogue.
- Variants become possible: a country's names and prices, or a clinic
  importing and exporting its own catalogue in the same format.
- `seed.py` went from about 2,500 lines to under 600, all of it logic.

### Bad / accepted trade-offs

- JSON carries no comments. The reasoning that used to sit next to a rule
  ("veneers are restorative work done for an aesthetic goal") now lives in
  the README beside the files, or nowhere.
- Treatments that draw on the tooth chart carry their drawing rules
  spelled out, which makes those entries long.
- A treatment shared by two disciplines appears in one file only; a
  reviewer of the other file has to know to look for it. The settings
  screen shows them under *Shared with …*.
- The sub-area of a treatment cannot be changed by a clinic.

## How to verify the rule still holds

`backend/tests/test_catalog_reference.py`: the files load; there is one
per discipline; codes are unique; every treatment names a known category,
discipline, sub-area and phase; every sub-area is used; and each
discipline's own first.
