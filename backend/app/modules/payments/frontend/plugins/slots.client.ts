import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'

/**
 * Slot registrations for the `payments` module.
 *
 * Hosts (`budget`) expose stable slot names. The slot registry is the
 * only contract — the budget module never imports payments code.
 */
export default defineNuxtPlugin(() => {
  // Tab of the host's Finanzas page. The host owns the page and the
  // sidebar entry; this module owns its own list and never learns about
  // its sibling tabs. Uninstalling the module removes the tab.
  registerSlot('finance.tabs', {
    id: 'payments.finance.tabs',
    component: defineAsyncComponent(() => import('../components/finance/PaymentsTab.vue')),
    permission: 'payments.record.read',
    labelKey: 'payments.nav.payments',
    order: 10
  })

  // Sibling tab: what has been collected, and what has not. The id is
  // `payments_receivables` rather than `payments` because the Finanzas page
  // derives the URL's tab key from the id's first segment, and two tabs
  // from one module would otherwise claim the same key.
  registerSlot('finance.tabs', {
    id: 'payments_receivables.finance.tabs',
    component: defineAsyncComponent(() => import('../components/finance/ReceivablesTab.vue')),
    permission: 'payments.record.read',
    labelKey: 'payments.nav.receivables',
    // Right after Cobros: what came in and what has not are one question
    // asked twice, and reading them as a pair is the point. `cashbox`
    // already claims 15.
    order: 12
  })

  // Resumen tiles. The Finanzas page owns the tab and knows nothing about
  // this module; it renders whatever `finance.summary` holds, in order.
  registerSlot('finance.summary', {
    id: 'payments.finance.summary.collected',
    component: defineAsyncComponent(() => import('../components/finance/SummaryCollected.vue')),
    permission: 'payments.reports.read',
    order: 10
  })

  registerSlot('finance.summary', {
    id: 'payments.finance.summary.receivable',
    component: defineAsyncComponent(() => import('../components/finance/SummaryReceivable.vue')),
    permission: 'payments.reports.read',
    order: 20
  })

  // No card in `budget.detail.sidebar` any more. The budget's money is
  // followed from its treatment plan, which the budget page now links to
  // in that spot; two places showing the same collections disagreed as
  // soon as a payment covered work outside the budget.
  // `BudgetPaymentsCard.vue` is left unregistered, not deleted.

  // Money view of a treatment plan. The plan exposes the slot name and
  // hands over `{ planId, patientId, budgetId, planStatus }`; it renders
  // nothing of its own here and never imports payments code.
  registerSlot('treatment_plan.detail.sidebar', {
    id: 'payments.treatment_plan.detail.sidebar.collections',
    component: defineAsyncComponent(
      () => import('../components/PlanCollectionsCard.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // "Cobrar" for one treatment of the plan, offered inside the treatment's
  // own detail dialog and right after it is marked done. The plan places the
  // button and hands over `{ patientId, patientName, budgetId, amount }`; it
  // never learns that a payment modal exists.
  registerSlot('treatment_plan.item.collect', {
    id: 'payments.treatment_plan.item.collect',
    component: defineAsyncComponent(
      () => import('../components/PlanItemCollectButton.vue')
    ),
    permission: 'payments.record.write',
    order: 10
  })

  // Agreed payment schedule of the plan. Sits beside the collections card
  // and answers the other money question: not "what can we charge for work
  // done" but "what did we agree to charge, and when".
  registerSlot('treatment_plan.detail.sidebar', {
    id: 'payments.treatment_plan.detail.sidebar.schedule',
    component: defineAsyncComponent(
      () => import('../components/PaymentScheduleCard.vue')
    ),
    permission: 'payments.record.read',
    order: 20
  })

  // Payments report card on /reports. Lets the reports module stay
  // unaware of payments while users still discover the dashboard from
  // the central reports landing.
  registerSlot('reports.categories', {
    id: 'payments.reports.categories.dashboard',
    component: defineAsyncComponent(
      () => import('../components/PaymentsReportEntry.vue')
    ),
    permission: 'payments.reports.read',
    order: 40
  })

  // Patient ledger sub-mode inside the patient detail "Administración"
  // tab. The patients module exposes the slot name and renders
  // `<ModuleSlot>`; it never imports anything from payments.
  registerSlot('patient.detail.administracion.payments', {
    id: 'payments.patient.detail.administracion.panel',
    component: defineAsyncComponent(
      () => import('../components/PatientPaymentsPanel.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // Patient Resumen — balance smart-card. Same slot contract pattern as
  // the panel above; the patients host page exposes the slot name and
  // renders <ModuleSlot> only.
  registerSlot('patient.summary.cards', {
    id: 'payments.patient.summary.cards.balance',
    component: defineAsyncComponent(
      () => import('../components/summary/BalanceCard.vue')
    ),
    permission: 'payments.record.read',
    order: 30
  })

  // /patients list — per-row debt badge. Host (`patients`) renders
  // <ModuleSlot name="patients.list.row.financial" :ctx="{ patient_id, summary }" />.
  registerSlot('patients.list.row.financial', {
    id: 'payments.patients.list.row.debt',
    component: defineAsyncComponent(
      () => import('../components/PatientListDebtCell.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /patients list — "Con deuda" filter chip in the toolbar.
  registerSlot('patients.list.filter', {
    id: 'payments.patients.list.filter.withDebt',
    component: defineAsyncComponent(
      () => import('../components/PatientListDebtFilter.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /budgets list — per-row collected/pending mini-progress + status chip.
  registerSlot('budget.list.row.payments', {
    id: 'payments.budget.list.row.collected',
    component: defineAsyncComponent(
      () => import('../components/BudgetListPaymentsCell.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })

  // /budgets list — payment-status multi-select chip in the toolbar.
  registerSlot('budget.list.filter', {
    id: 'payments.budget.list.filter.paymentStatus',
    component: defineAsyncComponent(
      () => import('../components/BudgetListPaymentsFilter.vue')
    ),
    permission: 'payments.record.read',
    order: 10
  })
})
