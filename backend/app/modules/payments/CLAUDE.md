# Payments module

Patient-centric collections, allocations to budgets / on-account,
refunds, patient ledger, and dental payment reports.

Issue #53. ADR 0010 documents the architectural inversion: billing
depends on payments, the reverse is forbidden. The link
``invoice ↔ payment`` lives in the billing module's own
``invoice_payments`` table; payments does not import billing.

## Public API

Routes mounted at `/api/v1/payments/`.

| Path | Method | Permission |
|---|---|---|
| `/` | GET | `payments.record.read` |
| `/` | POST | `payments.record.write` |
| `/{id}` | GET | `payments.record.read` |
| `/{id}/reallocate` | POST | `payments.record.write` |
| `/{id}/refunds` | GET | `payments.record.read` |
| `/{id}/refunds` | POST | `payments.record.refund` |
| `/patients/{patient_id}/ledger` | GET | `payments.record.read` |
| `/patients/{patient_id}/pending-charges` | GET | `payments.record.read` |
| `/budgets/{budget_id}/allocations` | GET | `payments.record.read` |
| `/summary/by-treatments` | POST | `payments.record.read` |
| `/schedules` | GET | `payments.record.read` |
| `/schedules` | POST | `payments.record.write` |
| `/schedules/{id}` | GET | `payments.record.read` |
| `/schedules/{id}` | PUT | `payments.record.write` |
| `/schedules/{id}` | DELETE | `payments.record.write` |
| `/reports/summary` | GET | `payments.reports.read` |
| `/reports/trends` | GET | `payments.reports.read` |
| `/reports/by-method` | GET | `payments.reports.read` |
| `/reports/by-professional` | GET | `payments.reports.read` |
| `/reports/aging-receivables` | GET | `payments.reports.read` |
| `/reports/refunds` | GET | `payments.reports.read` |

## Dependencies

`manifest.depends = ["patients", "budget"]`. **Never add billing** —
that would create a cycle (billing.depends includes payments). Read
ADR 0010 before touching the dependency list.

## Permissions

`payments.record.{read,write,refund}`, `payments.reports.read`.

Refund is admin/dentist by default. Clinic admins may grant
`payments.record.refund` to receptionists via the roles UI — no code
change required.

## Tools exposed

Agent tools in `tools.py` (wrap `PaymentReportsService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `payments_summary` | READ | `PaymentReportsService.summary` | `payments.reports.read` |
| `collections_by_method` | READ | `PaymentReportsService.by_method` | `payments.reports.read` |
| `record_payment` | WRITE | `workflow.record_payment` | `payments.record.write` |
| `patient_payment_history` | READ | `LedgerService.get_patient_ledger` (filtered) | `payments.record.read` |

**Off-books boundary.** These expose the **collection axis only** (gross
collected / refunded). They drop `clinic_receivable_total` /
`patient_credit_total` — "what's owed" is the invoiced-minus-collected
diff this module must never surface (see the gotcha below). Aging /
ledger-**balance** tools are deliberately NOT exposed to the agent:
`patient_payment_history` strips the ledger down to payments + refunds
(+ on-account balance, which is a subset of what was paid) and drops
`total_earned` / `patient_credit` / `clinic_receivable` before
returning. Enforced by tests in `tests/test_module_tools.py`.

## Events emitted

- `payment.recorded` — payload `{clinic_id, payment_id, patient_id, amount, currency, method, payment_date, occurred_at}`.
- `payment.allocated` — payload `{clinic_id, payment_id, allocation_id, target_type, target_id, amount, previous_target_type, previous_target_id, occurred_at}`. Fired on create and on reallocate.
- `payment.refunded` — payload `{clinic_id, payment_id, refund_id, amount, reason_code, occurred_at}`.

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `odontogram.treatment.performed` | `on_treatment_performed` | Upsert `PatientEarnedEntry` (single-session row, `source_session_id=NULL`) |
| `treatment_plan.item_session_completed` | `on_session_completed` | Upsert per-session `PatientEarnedEntry` keyed on `(treatment_id, source_session_id)`. Replaces the legacy `treatment_plan.treatment_completed` subscription since the multi-session feature — see ADR/changelog. |

Both handlers require `unit_price`/`price_snapshot` in the payload. If
the publisher omits it, the entry is skipped with a warning — see
gotchas below.

## Frontend slots consumed

| Slot | Component | Permission |
|---|---|---|
| `budget.detail.sidebar` | `BudgetPaymentsCard` (cobrado / pendiente / allocations + "Cobrar" CTA) | `payments.record.read` |
| `treatment_plan.detail.sidebar` | `PlanCollectionsCard` (pendiente de cobrar del paciente + "Cobrar") | `payments.record.read` |
| `treatment_plan.detail.sidebar` | `PaymentScheduleCard` (calendario pactado + plazos) | `payments.record.read` |
| `reports.categories` | `PaymentsReportEntry` (card on `/reports` linking to `/reports/payments`) | `payments.reports.read` |
| `patient.detail.administracion.payments` | `PatientPaymentsPanel` (patient ledger inside the Administración tab — KPIs + timeline + refund row menu + "Pendiente de cobrar" card) | `payments.record.read` |

Registered in `frontend/plugins/slots.client.ts`. Cards receive `ctx`
from the host page (`{ budget }`, `{ patient, patientId }`) and never
import anything from the host module's code — only the slot name and
the public endpoints.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=False`.
- Fiscal/contable retention forbids data deletion; uninstall is
  blocked by manifest.

## Gotchas

- **Devengado y calendario son dos vistas del mismo dinero, y nunca se
  suman.** El devengado responde «qué se debe por trabajo hecho»; el
  calendario, «qué se pactó cobrar y cuándo». Un caso de 19.020 MXN cobra casi
  todo antes de que exista casi nada del trabajo: la primera vista marca 0
  mientras la clínica va perfectamente al día. Los dos se saldan contra los
  mismos pagos, así que sumarlos duplica la factura del paciente.
- **Un calendario se puede renegociar aunque ya se haya cobrado.** Es la razón
  normal para tocarlo: «la paciente no puede con diciembre, párteselo». No
  corrompe nada porque el reparto se calcula, nunca se guarda — los plazos
  nuevos se vuelven a cubrir en orden con los mismos pagos. Si el total nuevo
  queda por debajo de lo ya cobrado, el sobrante sale como `unapplied` en vez
  de desaparecer. `instalments` es reemplazo completo cuando viene y no se
  toca cuando falta, igual que la plantilla de sesiones del catálogo.
- **El estado de un plazo se calcula, no se guarda.** Los pagos cubren los
  plazos en orden, igual que cubren los devengos. No hay columna `paid` que
  pueda desincronizarse del libro, y registrar un cobro actualiza las dos
  vistas sin tocar ninguna. `overdue` es cuestión de fecha, no de importe: un
  plazo medio pagado cuya fecha ya pasó sigue vencido.
- **Las rutas `/schedules` van declaradas antes que `/{payment_id}`.** FastAPI
  resuelve en orden de registro y «schedules» se parsearía como un id de pago.
- **`summary/by-treatments` es la vista de dinero de un plan.** Proyecta el
  mismo recorrido FIFO de `compute_pending_charges` sobre los tratamientos
  que pide el llamante, y devuelve estado por tratamiento **y** por sesión.
  El recorrido usa *todos* los devengos del paciente, no solo los pedidos: un
  pago hecho por otro plan ya consumió parte de lo que entregó, e ignorarlo
  daría por pendiente dinero que no lo está. Por eso `patient_id` es
  obligatorio y no se deduce de los tratamientos.
- **Los dos caminos de devengo nunca apuntan al mismo tratamiento.**
  `odontogram.treatment.performed` (fila `source_session_id=NULL`) y
  `treatment_plan.item_session_completed` (una fila por sesión) no chocan en
  la restricción única, así que nada impedía que ambos anotasen el mismo
  tratamiento — y completar una partida de plan dispara los dos. Regla, en
  `_upsert_earned_entry`: **manda el desglose por sesiones**; la fila de
  tratamiento completo es solo para trabajo que nunca pasó por sesiones, se
  omite si ya hay filas de sesión y se borra si las sesiones llegan después.
- **El `occurred_at` de un pago es medianoche de la clínica, no de UTC.**
  `payment_date` es una DATE y la línea de tiempo necesita un instante, así
  que hay que elegir cuál. `_clinic_midnight` usa `Clinic.timezone`, que
  llega como parámetro desde el router y desde `tools.py` —igual que
  `currency`— y nunca se consulta desde el servicio. Combinarlo a medianoche
  UTC, que es lo que hacía, adelantaba un día todo cobro de cualquier clínica
  al oeste de Greenwich.
- **Las ventanas de los informes se construyen con `_clinic_day_window`.**
  Regla general: donde un instante (`refunded_at`, `performed_at`) se compara
  con un día pedido, el límite es el de la clínica. Donde se compara
  `payment_date`, que ya es una DATE, no hay nada que convertir. Son
  semiabiertas `[inicio, fin)`: `datetime.max` deja fuera el último
  microsegundo del día.
- **Cualquier ruta literal va declarada antes que `/{payment_id}`.** Vale para
  `/schedules` y para `/reports/`: `/reports/refunds` estuvo devolviendo 422
  porque `/{payment_id}/refunds` se había registrado antes.
- **El día y la hora de cualquier apunte son los del calendario de la
  clínica, no los del lector.** El frontend formatea con `formatInstant`
  (`~~/app/utils/date`), que fija `timeZone: clinicTimezone`. Sin eso, una
  clínica de Madrid leída desde México muestra la víspera, y el ledger
  contradice el recibo que tiene el paciente delante. Vale igual para la
  hora: «Pendiente de cobrar» enseña la hora de la sesión para que recepción
  la coteje con la cita, y esa hora es la de la consulta.
- **No `is_voided` flag.** Total reverso is `Refund(amount=Payment.amount)`.
  Don't reintroduce the legacy flag — the report stack relies on
  Refund rows being the only adjustment vector.
- **No paid-vs-invoiced metrics.** Reports must not subtract `paid` from
  `invoiced` or `earned` from `invoiced`. Dental clinics legitimately
  leave some treatments off the invoice; exposing that diff documents
  the operative and is a stopper for adoption. See ADR 0010.
- **No imports from odontogram or treatment_plan.** Earned data enters
  through event payloads only. Add fields to the publisher when needed —
  the snapshot pattern is the contract.
- **Allocations sum invariant** is enforced in the service, not the DB.
  Schemas validate at the boundary so 4xx never reach the workflow.
- **Cross-clinic budgets** are rejected by the workflow. UI must filter
  budget pickers to current clinic.
- **`Clinic.currency` snapshot.** Payments capture the clinic currency
  at write time. If a clinic ever switches currency, historical
  payments stay in the old one (correct behaviour).

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0010-payments-as-primitive-module.md`

## CHANGELOG

See `./CHANGELOG.md`.
