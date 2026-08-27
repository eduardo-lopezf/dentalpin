# Changelog — catalog module

## Unreleased

- fix(money): `formatPrice` takes `Money`; the VAT edit form converts the
  rate at the boundary instead of assuming a number.

- fix(ui): catalog pagination works — same Nuxt UI v2-props-on-v4
  problem as media (`@update:model-value` never fires; the component
  emits `update:page`).

- feat(seed): a clinic created through `/api/v1/auth/setup` now gets its
  baseline catalog — VAT types, categories, items and specialties. Core
  publishes the new `clinic.created` event and this module seeds itself off
  it, so core keeps its hands off module imports (ADR 0003). The bus awaits
  handlers, so the catalog is queryable before setup returns its tokens.
  Previously onboarding created the clinic and nothing else, and no code path
  anywhere would ever fill it.

- fix(seed): add `scripts/backfill_catalog_specialties.py`. `cat_0004`/`cat_0006`
  create `specialties` empty and the only code that fills it is `seed_catalog`,
  reachable solely through `seed_demo.py` — which returns early when the demo
  clinic already exists. A deployment created before the specialty axis landed
  upgraded cleanly and then showed an empty specialty list forever. The script
  runs `seed_all_clinics` (previously dead code, no callers) and commits.

- feat(nav)!: "Tratamientos" is now a section with two surfaces instead of a
  single page. `/treatments` resolves per role and lands on the plan
  pipeline (`/treatments/plans`, owned by `treatment_plan`) because that is
  the daily task; the catalog moves to `/treatments/catalog`. A shared
  `TreatmentsSectionNav` lives here — `catalog` owns the route space and is
  non-removable, and `treatment_plan` already depends on it, so that is the
  legal coupling direction. The landing is permission-resolved rather than
  hardcoded: every role holds `catalog.read` but plans are gated separately,
  so someone without plan access is sent to the catalog instead of bounced
  onto a page they cannot open. The nav entry takes the pipeline's old slot
  (order 30) so the menu does not shift under people who use it daily.

- feat(catalog): `is_visible` on catalog items (migration `cat_0008`) curates
  which treatments the clinical `/treatments` page lists. Deliberately
  separate from `is_active`: a hidden treatment stays offered and billable,
  so budgets, the odontogram and past invoices keep working — hiding is a
  display choice, deactivating is a clinical one. Defaults to true, since
  defaulting to hidden would empty the page on upgrade and force an admin
  through every row before it works. Surfaced as a "Visible" checkbox column
  in both tabs of the settings catalog page; it is one flag per treatment,
  so ticking it under "Tipo de Tratamiento" shows it ticked under "Por
  Especialidad". Toggling is admin-only, and the page's "x of y" total
  counts listable treatments rather than the raw fetch.

- feat(ui): new `/treatments` page and "Tratamientos" nav entry
  (`catalog.read`, order 35). Clinical, read-only counterpart to
  `/settings/catalog`: filters the catalog by category × specialty × phase,
  all combinable, everything visible by default. A "only what my team
  performs" switch narrows to the specialties covered by active
  professionals — a filter, never a lock, since the catalog is also history
  (referrals, past treatments, last year's invoices). The roster is read
  over HTTP from the professionals API rather than joined in the backend:
  `catalog` is foundational with `depends: []`, so reaching into
  `professionals` from it would invert the dependency. Filtering runs
  client-side over one snapshot — a clinic catalog is a few hundred rows and
  multi-select filters that re-query per keystroke feel worse than they
  read.

- fix(catalog): seeded (`is_system`) treatments are editable again. `PUT
  /items/{id}` rejected them outright with 403, which froze the entire
  shipped catalog — all 129 items — for admins too: a clinic could not set
  its own price, change a duration, or even deactivate a treatment it does
  not offer, since deactivating is an update. Only `internal_code` stays
  locked on system items, because the seeder matches on it and renaming it
  would make the next seed run recreate the original as a duplicate. The
  route is gated by `catalog.write`, which only the admin role holds
  (dentist/hygienist/assistant/receptionist get `catalog.read` only), so
  editing stays admin-only. The modal now disables just the code field
  instead of six others.

- feat(phases): add the stage-of-care axis. `default_phase` on catalog items
  (migration `cat_0007`, nullable) with the vocabulary in
  `TREATMENT_PHASES`: diagnóstico, urgencia, preventivo, estabilización,
  rehabilitación, estética electiva, mantenimiento. Chosen over a single
  "correctivo" bucket, which would have held two thirds of the catalog and
  classified nothing; the largest bucket is now 35%, and `restauradora`
  splits into disease control (fillings) vs restoring function (crowns) vs
  elective (veneers). Seeded per category with per-code rules, and
  backfilled onto items that predate the axis.

- feat(specialties): seed the ten baseline disciplines and classify the
  whole catalog. `Specialty` gains `key` (migration `cat_0006`, unique per
  clinic where not null) so a renamed specialty is matched, not duplicated,
  on the next seed — the same reason `TreatmentCategory` has one. Assignment
  is a category baseline (`CATEGORY_SPECIALTIES`) plus per-code extras
  (`ITEM_SPECIALTY_EXTRAS`) for the cases a category cannot express:
  Implantología spans `cirugia` + `restauradora` + `protesis`, veneers are
  `restauradora` but aesthetic, PERIO-MAINT is hygienist work. Seeding is
  additive — it fills gaps and never removes a clinic's own assignments —
  and links treatments that predate the specialty axis, not just newly
  created ones. On the demo catalog: 10 specialties, 184 links, zero
  treatments left unclassified.

- feat(specialties): treatments can now be assigned to specialties.
  New `catalog_item_specialties` association table (migration
  `cat_0005`) — many-to-many, since a treatment may be performed under
  more than one discipline. `CatalogItemResponse` gained a
  `specialties` list; `GET /specialties/{id}/items` (`catalog.read`)
  and `PUT /specialties/{id}/items` (`catalog.admin`) list and replace
  the assignment, the PUT payload being authoritative. Frontend: the
  "Por Especialidad" tab now renders each specialty as a collapsible
  group of its treatments plus a "Sin especialidad" group, with a
  searchable assignment modal.

- feat(specialties): add a `Specialty` catalog entity (`specialties`
  table, migration `cat_0004`) independent from `TreatmentCategory` —
  a dental discipline (e.g. "Cirugía Oral y Maxilofacial") rather than
  a catalog browsing group. `SpecialtyService` + `/api/v1/catalog/specialties`
  CRUD (list/get gated by `catalog.read`, mutations by `catalog.admin`),
  soft-delete via `is_active`. Frontend: `useSpecialties()` composable
  and full create/edit/delete UI embedded in the "Por Especialidad" tab
  of the treatment catalog settings page. This only defines the
  specialty list — treatment assignment landed right after (see the
  `cat_0005` entry above); assigning specialties to dentists is still
  a separate follow-up.

- feat(ui): add view tabs to the treatment catalog settings page —
  "Tipo de Tratamiento" (existing grouped-by-category view) and
  "Por Especialidad" (specialty catalog CRUD + treatment assignment,
  see above).

- feat(tools): expose `list_catalog_items` + `get_catalog_item` READ
  agent tools (wrap `CatalogService`) so the copilot can read the
  treatment catalog — name, code, category, price, duration, scope.

- feat(seed): cover advanced surgical, periodontal and orthodontic
  techniques that any modern Spanish clinic offers and the Gesdén
  importer was previously dumping into ``Importado de Gesdén``. New
  catalog items: ``SURG-PRP`` (Plasma rico en plaquetas / PRGF),
  ``SURG-PERIIMP`` (tratamiento de periimplantitis), ``SURG-BONE-VERT``
  + ``SURG-BONE-HORIZ`` (aumento óseo vertical y horizontal),
  ``SURG-SINUS-CLOSED`` (elevación de seno cerrada / atraumática),
  ``PERIO-GINGIV`` (gingivectomía), ``PERIO-SURG-RESECT`` +
  ``PERIO-SURG-REGEN`` (cirugía periodontal resectiva y regenerativa),
  ``ORTO-TAD`` (microtornillo / anclaje esquelético temporal),
  ``ENDO-APICOFORM`` (apicoformación), ``PED-SPACE-COMPOUND``
  (mantenedor de espacio compuesto). Renames ``PED-FILL-TEMP`` from
  "Obturación en pieza temporal" to "Obturación en dentición
  temporal" — the standard Spanish wording, disambiguates from
  ``REST-TEMP`` (temporary filling material on any tooth).
- feat(seed): broaden coverage for Gesdén imports — add 36 treatments
  across diagnóstico (urgencia, segunda opinión, telerradiografía),
  preventivo (tartrectomía con curetaje, profilaxis infantil),
  restauradora (reconstrucción amplia, recementado de corona, corona
  sobre endodonciado, pilares de cicatrización/definitivo, reparación
  de obturación), endodoncia (apertura cameral urgente, recambio
  medicación, endo en temporal), periodoncia (curetaje por sextante,
  estudio periodontal, férula post-RAR), cirugía (injerto conectivo,
  alargamiento coronario, exéresis de quiste, exodoncia de incluido,
  regularización ósea), ortodoncia (cementado / descementado de
  bracket, separadores, expansor palatino), estética (reconstrucción
  estética, eliminación de pigmentación), prótesis (provisional
  removible, ajuste oclusal), odontopediatría (extracción / obturación
  en temporal, pulpectomía). Lifts the seed from 82 to 118 items so
  the migration_import fuzzy matcher finds a real destination instead
  of dumping treatments in ``Importado de Gesdén``.
- feat(seed): add catalog items for implant-supported crowns —
  ``REST-CROWN-IMPL-MC`` (metal-ceramic), ``REST-CROWN-IMPL-ZIR``
  (zirconia) and ``REST-CROWN-IMPL-PROV`` (provisional). They map to
  the new odontogram clinical types ``crown_on_implant`` and
  ``provisional_crown_on_implant``.
- feat(sessions): new ``CatalogItemSession`` entity defines named,
  priced steps for treatments billed in stages (e.g. crown: "Toma de
  medidas" 200€ + "Colocación" 600€). Sum of session prices must
  equal the item ``default_price`` (422 on mismatch). Updates replace
  the template atomically. Migration ``cat_0003`` adds the table.
  Frontend admin ``CatalogItemModal`` gets a "Sesiones" section with
  editor + sum-validation chip.
- perf(list): ``CatalogService.list_items`` now counts directly via
  ``COUNT(TreatmentCatalogItem.id)`` instead of materialising the
  joined data query as a subquery.
- fix(isolation): drop the cross-module imports of
  ``billing.InvoiceItem`` and ``budget.BudgetItem`` from
  ``CatalogService.get_popular_items``. Catalog is foundational
  (``manifest.depends = []``) — importing consumer-module models
  inverted the DAG and blocked uninstall of billing / budget. The
  usage ranking now reads the sibling tables through a single raw
  ``UNION ALL`` SQL fragment and falls back to the most recent
  active items when a clinic has no budgets / invoices yet.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Treatment catalog with categories.
- VAT types with versioning.
- Pricing rules in `pricing.py`.
- Idempotent seed in `seed.py`.
