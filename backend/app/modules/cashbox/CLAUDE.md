# Cashbox module

The clinic's till, complete: the movements (phase 1), the daily arqueo
(phase 2), the weekly / fortnightly / monthly cuts (phase 3) and the entries
that land in an already counted day (phase 4).

Out of scope on purpose: associate-dentist liquidation and terminal
commission. Both are worth having and both drag decisions of their own — see
`docs/technical/cashbox/overview.md`.

## What a corte de caja is, and is not

**Not a report.** `payments` already answers "how much came in this week,
by method, by professional" — `/reports/trends` even buckets by day, week
and month. What a corte adds is an **act**: someone counts the drawer,
declares what was in it, and the difference between that and what the
system expected is frozen. The number that matters is the one no query can
produce.

That is why the arqueo is daily and the period cuts are **views over the
daily closings, never recalculations from `payments`**: a fortnight
recalculated from payments looks perfectly clean with three days
unreconciled inside it, while one built from closings says "three days
still open", which is the thing the owner needs to know.

## Public API

Routes mounted at `/api/v1/cashbox/`.

| Method | Path | Permission |
|---|---|---|
| GET | `/movements` | `cashbox.movement.read` |
| GET | `/movements/totals?business_date=` | `cashbox.movement.read` |
| POST | `/movements` | `cashbox.movement.write` |
| GET | `/movements/{id}` | `cashbox.movement.read` |
| PUT | `/movements/{id}` | `cashbox.movement.write` |
| DELETE | `/movements/{id}` | `cashbox.movement.write` |
| GET | `/position?business_date=` | `cashbox.closing.read` |
| GET | `/closings` | `cashbox.closing.read` |
| POST | `/closings` | `cashbox.closing.write` |
| GET | `/closings/{id}` | `cashbox.closing.read` |
| POST | `/closings/{id}/reopen` | `cashbox.closing.reopen` |
| GET | `/periods?kind=&day=` | `cashbox.closing.read` |
| GET | `/late-entries?date_from=&date_to=` | `cashbox.closing.read` |
| POST | `/late-entries/acknowledge` | `cashbox.closing.write` |

`/movements` is not paginated on purpose: a till's rows are bounded by the
days asked for, and the screen asks for one.

`/position` carries `expected_cash`. **The counting screen must not render
it before the count is entered** — see the gotcha below. It is in the
payload because the same call feeds the history view.

`/periods` takes **any day inside** the period rather than its bounds: the
caller should not have to know where a Mexican quincena starts, and having
two places compute that is how they come to disagree.

## Dependencies

`manifest.depends = ["payments"]`. The arqueo reads `Payment` (cash
collections) and `Refund` (cash refunds) to compute the expected cash. It
never writes there, and `payments` knows nothing about this module.

## Permissions

`cashbox.movement.{read,write}` and `cashbox.closing.{read,write,reopen}`.

Reception writes and counts — they are who opens the drawer. **`reopen` is
not theirs**: it throws away a count a person made and signed off, which is
administration's call. Same narrowing `treatment_plan` applies to reopening
a plan. `hygienist` gets nothing: no business at the till.

## Frontend slots consumed

| Slot | Component | Permission |
|---|---|---|
| `finance.tabs` | `CashboxTab` (Caja: day picker, in/out totals, movement list, arqueo card) | `cashbox.movement.read` |

Order 15, after Cobros: the till is read in the context of what was
collected, and reception opens this screen at the end of the day rather
than through it.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False`. A cash count
  is an accounting record and fiscal retention forbids dropping it — the
  same reason `payments` is not removable. A clinic that never handles cash
  carries an unused tab, which is cheaper than a clinic that uninstalls and
  loses two years of arqueos.

## Gotchas

- **The amount is always positive; `direction` carries the sign.** A
  negative number in a till listing reads as a correction, and with a
  signed amount half the rows would carry one.
- **`business_date` is a DATE in the clinic's calendar**, never an instant.
  Using `created_at` would put a movement recorded at 00:10 into the wrong
  day's count for any clinic west of Greenwich.
- **In and out are never netted.** A day of 5.000 in and 5.000 out is not a
  quiet day, and one net figure tells both stories as zero. `day_totals`
  returns the two halves plus the count for exactly this reason, and the
  expected-cash arithmetic in phase 2 uses them separately.
- **A movement stops being editable when its day is closed.** The rule
  lives in `MovementService`, not the router, so the agent tools inherit
  it. `closing_id` is the flag; it is nullable with no FK until
  `cash_closings` exists (a constraint against a missing table will not
  create).
- **A `professional_payout` movement is not editable or deletable here.**
  `liquidations` writes those and points a foreign key at them. The refusal
  reads the **category**, never asking that module anything — this one knows
  nothing about settlements and must not start to. Deleting was already
  impossible (RESTRICT) but surfaced as a 500; editing was worse, because it
  succeeded and left a settlement claiming an amount the till never moved.
- **Deleting an open movement is a hard delete, deliberately.** It is not
  patient data and an open day has no accounting weight yet — a mistyped
  row the same minute it was typed should leave nothing behind. What
  survives the close is immutable instead, which is the protection that
  actually matters.
- **Clinic-day boundaries come from `app.core.utils.clinic_time`.** Those
  helpers were private to `payments/service.py` until this module needed
  the same boundaries; they were promoted rather than copied, because a
  second copy of that reasoning is a second chance to get it wrong. The
  asymmetry they encode: `Payment.payment_date` is already a DATE and
  needs no conversion, while `Refund.refunded_at` is an instant and must
  be resolved through the clinic's zone.
- **`/movements/totals` is declared before `/movements/{id}`.** FastAPI
  resolves in registration order and "totals" would parse as an id — the
  same trap that had `payments` returning 422 from `/reports/refunds`.
- **The router declares no prefix.** `_mount_one` mounts every module
  router at `/api/v1/<module name>`; declaring one here gives
  `/api/v1/cashbox/cashbox/...`.
- **A new module's migration branch must also be added to
  `alembic.ini`'s `version_locations`.** `discover_version_locations` finds
  it at runtime, but `alembic heads` / `alembic show` read the static list
  from the ini and will report the revision as missing. Not in
  `docs/checklists/new-module.md` yet.
- **Agent tools are read-only.** Recording a movement — or declaring a
  count — is a claim about physical money and an agent cannot witness it.
  Reads are exposed because "where did the cash go on Tuesday" and "how
  often are we short" are questions the clinic could not ask at all before.

### The arqueo (phase 2)

- **Do not show the expected figure before the count is entered.** This is
  the single decision that makes the feature worth having. Show someone
  "you should have 4.350" and then ask them to count, and they type 4.350:
  the difference is zero every day and a year of counts says nothing. The
  card renders the workings — collections, refunds, movements — and reveals
  the total they add up to only once a number has been typed.
- **Every figure on a closing is stored, not derived.** `expected_cash` is
  what the system believed at the moment of the count and stays that even
  after a payment is back-dated into the day. `snapshot` freezes the whole
  breakdown for the same reason: a period view must read the day as it was
  counted, never a fresh query over rows that have changed since.
- **Reopening supersedes, it does not delete.** The row becomes `reopened`
  and the next close writes a fresh one, so the history of counts survives.
  That history is the product: 20 short on a Tuesday is noise, 500 short
  every Friday is a signal, and a delete would erase the evidence.
- **One standing count per day is a partial unique index**, not a service
  check: `uq_cash_closing_standing_day ... WHERE status = 'closed'`. The
  superseded rows must not collide with the count that replaces them, and
  the database is a better place for that than a service remembering.
- **Only cash is counted.** A card batch settles itself against the
  terminal and a transfer reaches the bank on its own schedule; putting
  them in a drawer count is the commonest way this feature is made useless.
  They still appear under `collected_by_method`, as information.
- **A refund's method can differ from its payment's.** A card payment
  handed back in notes still empties the drawer, and only `Refund.method`
  says whether it did.
- **`ClosingService.get` uses `populate_existing`.** It is the read that
  runs straight after a write: without it the identity map hands back the
  instance as it was and a reopen answers `reopener: null` while the
  database holds the user who did it. Same trap `PlanTemplateService.get`
  documents.
- **The opening float chains from the last *standing* count before the
  day**, not from literally yesterday. Clinics close on Sundays, and a
  Monday whose float reset to zero would report the whole drawer missing.
- **"Today" is the clinic's, not the server's.** A UTC container is already
  on tomorrow while a clinic at UTC-6 is still working, so the
  future-day refusal resolves the current day through `clinic_date`.
- **`formatInstant` goes through `toLocaleDateString`**, which throws on
  `timeStyle`. Pass field options (`day`, `month`, `hour`, `minute`) — a
  throw inside a template unmounts the card rather than showing an error.

### The period cut (phase 3)

- **Assembled from the closings, never recalculated from `payments`.** This
  is the decision the whole phase turns on. Recomputed from payments, a
  fortnight with three uncounted days inside it looks immaculate; built
  from closings it can say *three days still to count*, which is the
  sentence a clinic owner actually needs. Every money figure is a sum of
  frozen `snapshot` values.
- **A pending day is a day money moved and nobody counted**, not any
  calendar day without a closing. A clinic that shuts on Sunday would
  otherwise be told it is four days behind every month; the warning would
  be wrong every time and nobody would read it within a fortnight. A day
  qualifies on cash taken, cash handed back, or a movement recorded — a
  card-only day never enters the drawer, so there is nothing to count.
- **The quincena is calendar, not rolling**: the 1st-15th and the 16th to
  the end of the month, because that is when payroll is paid. Every
  fourteen days drifts off the month by March and the report stops lining
  up with the only thing it is for. `period_bounds` is pure and unit-tested
  precisely here.
- **The week runs Monday to Sunday**, matching what `payments`' `trends`
  already buckets by, so the app has one week and not two.
- **`difference_total` nets on purpose, and `days_off` is why that is
  safe.** A fortnight 50 short one day and 50 over the next does balance,
  and saying so is honest; what would not be honest is letting it read as a
  quiet fortnight. The count of days that did not match is the figure worth
  watching, and the per-day list beside it is the pattern.

### Late entries (phase 4)

- **Back-dating into a counted day is allowed.** Refusing it only makes
  people file the money under today and lie about the date, which is worse
  than a late entry anybody can see. The signed count keeps its figures and
  the entry is surfaced instead.
- **What makes an entry late is not the same test for each kind**, which is
  why `LateEntryService.list` is not one query: a payment or a refund is
  late when it was *written* after the day was signed
  (`created_at > closing.closed_at`); a movement is late when its day is
  closed and it still carries no `closing_id`, since closing stamps every
  open row of the day.
- **An acknowledgement is required to clear one**, and the resolution text
  cannot be blank. Without somewhere to record *seen, it goes into next
  week's* the list only grows — and a warning that is always on is a
  warning nobody reads, the same failure that kills an arqueo whose
  difference is never zero. The card hides itself entirely when the list is
  empty, for the same reason.
- **Acknowledging is `closing.write`, not `closing.reopen`.** Deciding that
  a late entry rolls into the next count is reception's call and changes
  nothing that was signed; reopening the day is the other answer and stays
  with administration.
- **`LateEntryAck` addresses its entry by `(entry_kind, entry_id)`, not by
  a foreign key.** Two of the three kinds live in `payments`, and an FK
  from here would be a dependency the manifest does not declare.
- **No patient identity in the payload.** This module depends on `payments`
  and not on `patients`; a name would be both an undeclared dependency and
  PII in a payload that does not need it. The reference and the amount are
  enough to find the row in Cobros, which is where the person belongs.

## Testing

71 backend tests in `backend/tests/modules/cashbox/`, each building its own
data, plus two in `frontend/tests/e2e/tablet-touch.spec.ts`.

**The e2e assertions are structural on purpose.** `seed-demo.sh` creates no
movements and no arqueos — it cannot, because a count is something a person
does — so a test that expected a figure would pass on a developer's database
and fail in CI. They also drive a **day far older than anything the seed
writes** rather than today: a developer's database has real arqueos in it,
and a day that happens to be counted already hides the button the test needs,
failing locally while passing in CI.

One of the two pins the rule the whole feature rests on — the expected figure
is not revealed until a count is entered — and needs no data at all to do it.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `cash_movements` | READ | `MovementService.list` | `cashbox.movement.read` |
| `cash_movements_day_totals` | READ | `MovementService.day_totals` | `cashbox.movement.read` |
| `cash_closings` | READ | `ClosingService.list` | `cashbox.closing.read` |
| `cash_period_summary` | READ | `PeriodService.summary` | `cashbox.closing.read` |

`cash_movements` and `cash_closings` set `exposes_free_text=True`:
`concept` and `notes` are whatever the person at the counter typed.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0010-payments-as-primitive-module.md`
- `docs/adr/0018-install-state-is-the-mount-authority.md`

## CHANGELOG

See `./CHANGELOG.md`.
