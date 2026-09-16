# Liquidations module

Settling with associate dentists. Optional (`auto_install=False`): not every
clinic has associates on a percentage, and the ones that do not should not
carry the screen.

## The two numbers, which are not the same number

An associate on a percentage is paid from one of two figures:

- **earned** — the work they performed, priced. Comes straight off
  `PatientEarnedEntry`, which already carries `professional_id`.
- **collected** — what the patient has actually paid *for that work*.

On a 19.000 MXN orthognathic case those two are months apart. Paying a
percentage of the first means the clinic hands out money it has not
received; paying on the second means the associate carries part of the
collection risk. Most Mexican clinics do the second, so `collected` is the
default basis — but **both are computed and both are shown**, because
neither can be judged without the other, and which one a given professional
is paid on is an arrangement the clinic records per person.

## How money is attributed to a professional

There is no foreign key from a payment to the work it paid for. `payments`
settles the two FIFO — a patient's money covers their oldest charges first
— and `LedgerService.coverage_by_earned_entry` projects that walk onto the
entries themselves. Since an entry carries the professional who did the
work, covering the entries is what attributes the money.

**The walk runs over all of a patient's entries, not only this
professional's.** A patient who paid 6.000 against last month's fillings has
nothing left for this month's surgeon, and a walk restricted to one
professional would credit the same money twice. That is why the coverage
reader lives in `payments` and not here.

## Public API

Routes mounted at `/api/v1/liquidations/`.

| Method | Path | Permission |
|---|---|---|
| GET | `/commissions` | `liquidations.settlement.read` |
| PUT | `/commissions/{professional_id}` | `liquidations.commission.write` |
| GET | `/preview?professional_id=&date_from=&date_to=` | `liquidations.settlement.read` |
| GET | `` (list) | `liquidations.settlement.read` |
| POST | `` (issue) | `liquidations.settlement.issue` |
| GET | `/{id}` | `liquidations.settlement.read` |
| POST | `/{id}/pay` | `liquidations.settlement.issue` |
| POST | `/{id}/unpay` | `liquidations.settlement.issue` |

## Dependencies

`manifest.depends = ["payments", "professionals", "cashbox"]`. Reads the
earned ledger and the FIFO coverage from the first, and who is being settled
with from the second; it writes to neither. **`cashbox` is the one it writes
to**: paying a settlement in cash empties the drawer.

**Not `patients`.** A settlement goes to an associate and names the work,
not the people, so there is no patient identity anywhere in the payload.

## Permissions

`settlement.read`, `settlement.issue`, `commission.write`.

A dentist gets `settlement.read` — they can see what they are owed. The
percentage itself and the act of issuing are the owner's, so `admin` holds
`commission.write` and `settlement.issue`.

**Paying reuses `settlement.issue`** rather than adding a fourth grant.
Both are the owner deciding money moves, and a permission that every holder
of another also holds is flexibility nobody asked for. Split it if a clinic
ever wants a manager who can produce the document but not hand over cash.

## Frontend slots consumed

| Slot | Component | Permission |
|---|---|---|
| `finance.tabs` | `LiquidationsTab` | `liquidations.settlement.read` |

Order 60, last of the finance tabs: settling is a fortnightly act, not a
daily one, and the tabs are ordered by how often they are opened.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=False`. An issued
  settlement is what somebody was paid on; fiscal retention forbids dropping
  it, the same reason `payments` and `cashbox` are not removable.

## Gotchas

- **Both axes travel together everywhere.** Any surface that shows one
  without the other invites a clinic to pay a percentage of money it has
  not received. The screen marks which one the percentage is taken on.
- **Issuing freezes everything.** `lines`, `percent` and `basis` are copied
  onto the `Liquidation` at issue time. A patient paying tomorrow for work
  done last fortnight must not change what somebody was already paid, and
  neither must a percentage renegotiated in March.
- **The arrangement is mutable and that is safe** precisely because of the
  above. Same principle as the arqueo in `cashbox`: the document is the
  record, the setting is only what the next one starts from.
- **A missing arrangement is reported, not assumed.** The preview returns
  the work with `missing_commission=true` and a zero share; issuing is
  refused. Handing somebody a confident zero is worse than saying the
  percentage has not been agreed.
- **Sessions fold into their treatment.** A multi-session item earns once
  per session; an associate reads a job, not a row per visit.
- **The period window is the clinic's.** `performed_at` is an instant and
  the period is a run of clinic days, so it goes through
  `app.core.utils.clinic_time` like every other date window in the project.
- **One settlement per exact period per professional.** Re-issuing is
  refused rather than silently producing a second document; the preview
  reports `issued_id` so the screen can say so before anybody tries.
- **The migration uses `depends_on`, not a threaded `down_revision`.** Both
  tables FK to `professionals.id`, so that module must migrate first — but
  hanging `down_revision` off the professionals head would merge the
  branches and drag this module into `alembic downgrade professionals@base`
  (issue #56, ADR 0002). `depends_on = ("professionals",)` orders them
  without merging.
- **One percentage per professional in this version.** Clinics that split
  by discipline — 40 % on orthodontics, 50 % on surgery — are real; the
  extension point is a child table keyed on the catalog category and
  nothing here has to change for it.
- **Agent tools are read-only.** What an associate is owed is a number a
  person hands over and stands behind.

### Paying the settlement

- **Writing the till movement is a direct call, in the same transaction,
  and the event bus was the wrong answer.** ADR 0003 makes events the
  default for cross-module *reactions*, but this is not a reaction: the
  payout and the movement are one fact seen twice. A handler running after
  the commit can fail — the bus records it and never retries — and what
  that leaves is a settlement reading *paid* with no money out of the
  drawer, the exact silent divergence the cashbox work exists to prevent.
  The precedent is `treatment_plan.confirm()` calling
  `BudgetService.create_from_plan_snapshot` synchronously, documented there
  as the carve-out.
- **Only cash touches the drawer.** A transfer reaches the associate's bank
  without the till opening, and inventing a movement for it would make the
  next arqueo short by the whole payout — a bug that looks like theft.
- **The payout movement is not editable from the till.** `cashbox` refuses
  to edit or delete a `professional_payout` row, reading the category
  rather than asking this module anything. Deleting was already impossible
  (RESTRICT) but arrived as a 500; editing was worse, because it succeeded
  and left the settlement claiming an amount the till never moved.
- **Undoing exists, and stops where the till stops it.** An irreversible
  mistaken payout is what makes people distrust a screen — but once the day
  has been counted the movement is inside a number somebody signed, and the
  way back is to reopen the day. Same rule as every other edit in `cashbox`.
- **A payout on a day already counted is a late entry**, handled by
  `cashbox` phase 4 with no code here. The loop composes rather than
  special-casing.

## Testing

32 backend tests in `backend/tests/modules/liquidations/`, each building its
own data — none of them reads the demo seed.

**There is no end-to-end coverage of the tab, and it is not an oversight.**
The module is `auto_install=False`, so it is not mounted in the environment
the Playwright suite runs against; a test would find no tab. Installing it
from the test is not an option either — `POST /modules/{name}/install`
answers `requires_restart`, and the suite cannot restart the app.

The two ways to close this, when it is worth closing:

- seed an installed `liquidations` for the e2e environment specifically, or
- have the suite drive the module admin screen and restart, which is a much
  heavier harness than the tab deserves.

Until then the screen is covered by hand and by the backend suite under it.
`cashbox`, which is `auto_install=True`, is covered in
`frontend/tests/e2e/tablet-touch.spec.ts`.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `liquidation_preview` | READ | `LiquidationService.preview` | `liquidations.settlement.read` |

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0010-payments-as-primitive-module.md`

## CHANGELOG

See `./CHANGELOG.md`.
