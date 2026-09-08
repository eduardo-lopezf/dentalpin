# payments — CHANGELOG

## Unreleased

- feat(ui): Cobros no longer has a sidebar entry of its own. Cobros,
  Presupuestos and Facturas are now the three tabs of a single
  **Finanzas** entry, placed after Profesionales, in that order. This
  module contributes its list through the `finance.tabs` slot and
  declares the shared nav entry in its manifest, so the entry survives
  while any of the three is installed and disappears with the last one —
  no cross-module import, and the mount authority stays
  `core_module.state` (ADR 0018). `/payments` keeps working as a redirect.
- feat(calendario): **editar un calendario ya pactado**, en vez de anularlo y
  rehacerlo. `PUT /payments/schedules/{id}` reemplaza los plazos, y el
  diálogo arranca de lo acordado —no de un reparto nuevo—, porque la razón
  para tocarlo suele ser «la paciente no puede con diciembre» y el resto debe
  sobrevivir. Se puede renegociar aunque ya se haya cobrado: el reparto se
  calcula, así que el dinero cobrado vuelve a cubrir los plazos nuevos en
  orden, y si el total baja por debajo de lo pagado el sobrante sale como
  pagado por adelantado.

  Cada fila puede quitarse o **añadir otra debajo** —no al final—, que es lo
  que hace falta para partir un plazo en dos sin que las fechas queden
  desordenadas.

- feat(calendario): calendarios de pago pactados. El libro de devengos
  responde «qué se debe por trabajo hecho», que es la pregunta correcta para
  una obturación y la equivocada para una ortognática de 19.020 MXN, donde el
  dinero se pacta por adelantado y se cobra mucho antes de que exista casi
  nada del trabajo. Un calendario guarda ese acuerdo: plazos con importe,
  etiqueta y fecha opcional — «antes de la cirugía» es un hito real sin fecha.
  Nuevas tablas `payment_schedules` y `payment_schedule_instalments`
  (`pay_0004`) y endpoints bajo `/payments/schedules`.

  El estado de cada plazo **se calcula**, no se guarda: los pagos los cubren
  en orden, igual que cubren los devengos, así que no hay columna que pueda
  desincronizarse del libro. Las dos vistas se saldan contra los mismos pagos
  y no deben sumarse nunca.

- feat(calendario): cada plazo lleva **etiqueta, fecha e importe editables**.
  El reparto elige cuántos plazos y propone un reparto; los importes se
  ajustan a mano, que es lo que permite pactos reales como «5.000 a la firma y
  el resto en seis mensualidades». El aviso de descuadre pasa así a servir
  para algo: antes nunca saltaba porque los repartos siempre cuadraban, y
  ahora bloquea guardar mientras los plazos no sumen el total del plan. Un
  importe de cero o negativo también bloquea, con su motivo.

- feat(calendario): cada plazo lleva **etiqueta y fecha editables**. El
  reparto escribe el primer borrador y a partir de ahí las líneas son de la
  clínica: «Anticipo a la firma», «Antes de la cirugía», «Al alta
  quirúrgica». La fecha se puede dejar en blanco —un hito sin fecha es lo
  normal, no un error de validación— y el campo vacío se envía como `null`,
  no como cadena vacía.

- feat(calendario): tarjeta en el plan con los repartos que sólo el plan puede
  calcular — por fases (cada fase, su precio), 30/40/30 y mensual — y aviso si
  los plazos no cuadran con el total del plan. El reparto redondea a la baja y
  deja el céntimo sobrante en el primer plazo, para no descubrir una deuda de
  0,01 al final de un caso de dos años.

- feat(cobros): `POST /payments/summary/by-treatments` — estado de cobro por
  tratamiento y por sesión para un paciente, con el mismo reparto FIFO que
  «pendiente de cobrar». Permite que un plan de tratamiento enseñe el dinero
  sin importar nada de payments, igual que ya hacían las listas de
  presupuestos y pacientes.

- feat(cobros): tarjeta en el slot `treatment_plan.detail.sidebar` — lo
  pendiente de cobrar del paciente y el botón «Cobrar», que abre el modal ya
  con el importe sugerido y el presupuesto del plan.

- fix(devengo): **cada tratamiento completado desde un plan se registraba dos
  veces, al doble de dinero.** Al terminar la última sesión se publica
  `treatment_plan.item_session_completed`, y acto seguido la partida se
  finaliza, ejecuta el `Treatment` y publica
  `odontogram.treatment.performed`; los dos manejadores apuntaban el mismo
  tratamiento y la restricción única no lo impedía, porque `NULL` y un
  `session_id` son claves distintas. Una endodoncia de 380,00 aparecía como
  760,00 en «pendiente de cobrar». Ahora manda el desglose por sesiones: la
  fila de tratamiento completo solo existe para trabajo que nunca pasó por
  sesiones, y si llega después de las sesiones se descarta (y si llegó antes,
  se sustituye). Cubierto por `tests/modules/payments/test_earned_no_double_booking.py`.


- fix(security): `GET /payments/patients/{patient_id}/ledger` and
  `.../pending-charges` accepted a `patient_id` from any clinic.
  The aggregation itself was correctly scoped by `clinic_id` — the
  response was all zeros, so nothing leaked — but the patient's ownership
  was never checked, so the route answered about a patient it should not
  have been able to name. `pending-charges` was not a sweep finding — it
  returns a list, so a foreign id came back as `200 []` and disclosed
  nothing — but it is the same pattern next door, and the frontend
  already degrades a failed fetch to an empty list, so the 404 is
  invisible to the UI. Both now 404, via the `_ensure_patient` helper that
  mirrors odontogram / periodontogram, minus their `status != "archived"`
  clause: money outlives the chart, so an archived patient's ledger must
  stay readable. Found by `tests/test_cross_tenant_isolation.py`
  ([ADR 0029](../../../../docs/adr/0029-security-invariants-with-chokepoints.md)).


- feat(privacy): `get_subject_contributors()` — este módulo ya responde
  cuando un paciente ejerce portabilidad o supresión
  ([ADR 0026](../../../../docs/adr/0026-subject-rights-are-a-module-contract.md)).
  Cobros, asignaciones, histórico y devoluciones. Conservación fiscal.

- fix(money): the refund modal's seeded amount is typed `Money` — it comes
  straight from the payment's net amount, a Decimal string.

- fix(ui): removed the patient-panel row menu's "detail" entry, which
  linked to `/payments/{id}` — a page that exists in no layer, so it
  always 404'd. The menu now renders only when it has something to
  offer (audit S5, dead affordance).

- fix(events): publish through ``event_bus.publish_after_commit(db, ...)``
  instead of announcing from inside the caller's open transaction.
  Handlers read through their own sessions, so a flushed-but-uncommitted
  row was invisible to them (audit S2). See
  [ADR 0019](../../../../docs/adr/0019-events-publish-after-commit.md).

- fix(security): lock the payment row `FOR UPDATE` before the refund
  cap check (audit S3/C1, #97). Two concurrent refunds could both read
  `already_refunded` before either inserted, letting Σrefund exceed
  `payment.amount` and driving `net_paid` negative. The row lock
  serializes them so the cap holds.

- feat(agents): two new copilot tools — `record_payment` (WRITE, wraps
  `workflow.record_payment`, allocation-sum errors surfaced structurally)
  and `patient_payment_history` (READ, collection axis only: drops
  `total_earned`/`patient_credit`/`clinic_receivable` from the ledger).

- feat(agents): expose `tools.py` — `payments_summary`,
  `collections_by_method` (READ). Off-books: **collection-axis only**
  (gross collected/refunded; never receivable/credit/pending). Issue #81
  P0 batch.

- chore(migration ``pay_0003``): drop the ``ck_earned_amount_nonneg``
  check on ``patient_earned_entries``. Migration imports need to land
  Gesdén's ``Nota Económica`` credit-note rows (negative
  ``TtosMed.Importe``) so the patient ledger reconciles with the
  source's running total. Event-driven publishers still emit
  non-negative amounts in normal operation.
- feat(earned-per-session): ``PatientEarnedEntry`` gains
  ``source_session_id`` + ``description`` and is now keyed on
  ``(treatment_id, source_session_id)`` so multi-session treatments
  produce one row per session. Replaced the ``treatment_plan
  .treatment_completed`` subscription with
  ``treatment_plan.item_session_completed`` (handler
  ``on_session_completed``). Migration ``pay_0002`` adds the column,
  best-effort backfills ``source_session_id`` from
  ``planned_treatment_item_sessions`` when the module is installed, and
  swaps the unique index.
- feat(pending-charges): new ``GET /payments/patients/{id}/pending-charges``
  returns the FIFO-virtual list of earned entries not yet covered by
  net payments. ``PatientPaymentsPanel`` renders a "Pendiente de
  cobrar" card at the top of the patient ``Pagos`` tab so reception
  can collect when the patient leaves the box, with the amount
  pre-filled in ``PaymentCreateModal``.
- refactor(perms): migrate hardcoded ``can('payments.record.{write,refund,read}')`` strings in the payments list, ``PatientPaymentsPanel`` and ``BudgetPaymentsCard`` to ``PERMISSIONS.payments.*`` (new entries in the host permissions config).
- docs(user-manual): reescribir pantalla /payments e index del módulo (ES + EN).

### Changed (reports dashboard redesign, 2026-05-17)

- `/reports/payments` reescrito con calm-design: hero KPIs (cobrado
  neto + sparkline + delta vs periodo anterior, pendiente con mini
  bars por bucket de antigüedad), KPIs secundarios con sparkline,
  tendencia full-width (consume por primera vez
  `GET /reports/trends`), donut por método, top profesionales,
  aging detail y devoluciones por motivo. Toda interacción dispara
  drill-down a `/payments` (o `/patients` para aging) con el rango
  preservado por query string. Sin dependencias nuevas: viz
  resuelta con SVG en `frontend/app/components/charts/*`
  (`Sparkline`, `BarRow`, `DonutChart`, `TrendAreaChart`), genéricos
  y reusables por cualquier módulo. Mantiene el invariante
  off-books (sin cruces paid↔invoiced).
- `FilterDateRange` con presets reemplaza los `UInput type=date`
  crudos; `useCurrency` reemplaza el `Intl.NumberFormat` inline y
  el fallback hardcoded a `'EUR'`.
- i18n del módulo: nuevas keys bajo `payments.reports.*`
  (granularity, hero, trend, empty, drilldown, bucket, refresh,
  hints) en ES y EN.

### Added (lists redesign, 2026-05-14)

- `POST /api/v1/payments/summary/by-budgets` — bulk per-budget
  collected/pending/payment_status (cap 100 ids). Off-books safe.
- `POST /api/v1/payments/summary/by-patients` — bulk per-patient
  total_paid/debt/on_account (cap 100 ids). Off-books safe.
- `GET  /api/v1/payments/filters/budgets-by-status` — clinic-wide
  budget id set by payment status (cap 1000 ids, `truncated` flag).
- `GET  /api/v1/payments/filters/patients-with-debt` — clinic-wide
  patient id set with debt ≥ min_debt (cap 1000 ids).
- New slot fillers registered: `patients.list.row.financial`,
  `patients.list.filter`, `budget.list.row.payments`,
  `budget.list.filter`. Enables /patients debt column + "Con deuda"
  filter and /budgets payment-progress column + "Cobro" filter
  without violating module isolation.
- `GET /api/v1/payments` accepts new params: `has_refunds`,
  `has_unallocated`, `amount_min`, `amount_max`, `sort=field:dir`
  (whitelist: `payment_date`, `amount`, `created_at`).
- `/payments` UI rewritten on top of `DataListLayout` + `FilterBar`
  + `useListQuery`. Chips for method, date range with presets,
  paciente como autocomplete (sustituye al campo UUID).
- Initial module skeleton (issue #53).
- Models: `Payment`, `PaymentAllocation`, `Refund`, `PatientEarnedEntry`, `PaymentHistory`.
- Workflow: `record_payment`, `reallocate_payment`, `refund_payment`.
- Read services: `PaymentService`, `PaymentReadService`, `LedgerService`, `PaymentReportsService`.
- Endpoints under `/api/v1/payments/` covering CRUD, refunds, ledger, per-budget allocations, and reports (summary, by-method, by-professional, aging-receivables, refunds, trends).
- Events emitted: `payment.recorded`, `payment.allocated`, `payment.refunded`.
- Events consumed: `odontogram.treatment.performed`, `treatment_plan.treatment_completed` → upsert into `patient_earned_entries`.
- Migration `pay_0001_initial` on the `payments` branch (chains after `bud_0003`).
- `BudgetPaymentsCard` redesign compacto: resumen `Cobrado / Total` con barra de progreso, estado de pendiente en una línea, historial con icono de método + fecha relativa, único CTA "Cobrar" en el header (oculto cuando saldado). Mueve la tarjeta al top del sidebar del detalle de presupuesto (antes caía al fondo del grid).
- `AllocationResponse` ahora expone `method` (del pago padre) — aditivo, sin queries nuevas (ya estaba joinedloaded).
- `BudgetCollectModal` usa `useCurrency().format` en lugar de un `Intl.NumberFormat` inline; prop `currency` retirado (era vestigial).
- `PatientPaymentsPanel` registrado en el slot `patient.detail.administracion.payments` (host: módulo `patients`). Surfacing del ledger del paciente (banner deuda/crédito, KPIs `total_paid` / `clinic_receivable` / `on_account_balance`, sidebar con saldo a favor y último pago, timeline cronológico con menú overflow por pago para reembolsar) dentro del tab Administración de la ficha. Consume `GET /payments/patients/{id}/ledger` ya existente; sin endpoints nuevos.
- `RefundConfirmModal` — formulario corto (importe, método, motivo, nota) usado desde el menú overflow del timeline para `POST /payments/{id}/refunds`.
