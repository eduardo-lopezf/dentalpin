# Changelog — catalog module

## Unreleased

- fix(permissions): the catalog UI asked `isAdmin` while the API asks
  `catalog.write` / `catalog.admin`. Two different questions that happen
  to coincide, because only the admin role holds either grant — so
  granting `catalog.write` to a dentist would have let the API through
  while the UI kept the buttons hidden. Every guard in
  `settings/catalog`, `settings/vat-types` and `treatments/catalog` now
  asks for the grant. **No behaviour change today**: the default is
  unchanged and only `admin` can write.

- fix(permissions): `CatalogItemModal` guards the action, not just the
  trigger. It had no check of its own and relied on callers only opening
  it for admins; a caller added later that forgot would hand the user a
  full form and a 403 on save. The permission is now the first
  `blockingReason`, so the reason is shown rather than merely enforced.

- docs: filled in `docs/technical/catalog/permissions.md`, which was a
  scaffolded stub — every endpoint is now listed under the grant that
  gates it.

- feat(catalog): the alta form asks four questions instead of fifteen.
  Name, treatment type, who performs it and where in the mouth it applies —
  everything else is deduced and shown in a reviewable panel. The tabs are
  gone: a dentist adds a treatment a handful of times a year and needs to see
  it whole. Derivation tables live in
  `frontend/config/treatmentDefaults.ts`, covered by
  `frontend/tests/catalog/treatmentDefaults.test.ts`.

  From the type come the specialty, the plan phase, the odontogram bar tab and
  the chart type; from "where it applies" come the scope, whether surfaces are
  asked for, and the pricing strategy. `is_diagnostic` follows the type and
  the internal code is generated from type + name, so nobody mints a unique
  key by hand. The mapping is always sent — without one the treatment never
  reaches the plan builder — and is surfaced in the panel rather than set
  silently. Cost price leaves the form entirely: nothing reads it, and the
  column stays for the day a margin report wants it.

- feat(catalog): "where it applies" now offers only the placements that mean
  something for the chosen type. Endodontics is a single tooth and nothing
  else, so the row states it instead of offering five buttons; diagnosis is a
  whole mouth or one tooth — a periapical radiograph is of a tooth, which is
  why it cannot be pinned to the mouth. Kinds that are a single act
  (diagnosis, prevention) no longer offer session billing: a consultation or a
  fluoride application either happens or it does not.

  Editing is the exception to the constraint. An item already saved outside
  its type's list keeps its placement offered, so opening and saving an old
  record never migrates its scope — `Férula de descarga` is a real case, an
  arch-wide item filed under Restauradora.

- fix(catalog UI): a per-tooth treatment could not be saved at all. The alta
  form sent `odontogram_mapping.visualization_rules` as rule names
  (`["lateral_icon"]`) where the column stores layer objects
  (`[{"layer": "lateral_icon"}]`), so the API answered 422 and the toast said
  only "Error al crear tratamiento". Whole-mouth items send an empty list and
  were unaffected, which is why the first four fichas saved and MXF-CIR-01 did
  not. The form had its own copy of the loop; both call sites now share
  `getVisualizationRuleLayers`, and `OdontogramMapping` no longer types the
  field as `string[]` — the wrong type is what let this compile.

- fix(catalog UI): the form says why it cannot be saved. "Crear" was disabled
  with no explanation anywhere, which is indistinguishable from a broken
  button — and the session template makes it easy to hit, since every row has
  to be named and the eight of them have to add up to the exact total before
  anything happens. The reason now sits next to the button: which field is
  missing, or "las sesiones suman 0,00 y el precio es 9.500,00".

- fix(catalog UI): "Nuevo tratamiento" opens on a clean form again. The
  populate step watched `props.item`, which stays null across two creations in
  a row — null to null is not a change, so the second form opened still
  carrying the first one's answers. It now also runs when the modal opens.

- fix(catalog UI): the chart type is a dropdown of the types that fit, not a
  free text box. Correcting the suggestion used to mean knowing the value is
  spelled `imaging` — nothing on screen said so. The shortlist is narrowed by
  type and placement: twelve findings for a tooth-scoped diagnostic item, the
  four visit-level types for a whole-mouth one, plus the skeletal ones for
  whole-mouth surgery. Labels are the localized names, never the identifiers.

- fix(catalog UI): the field was labelled "Tipo de tratamiento", the same as
  the item's own type two rows above. It is now "Dibujo en el odontograma",
  matching the row it feeds in the derived panel — one concept, one name.

- fix(catalog UI): picking a type on a new treatment now carries its placement
  with it, so Diagnóstico lands on "toda la boca" instead of leaving "un
  diente completo" over from the previous type. The watcher used to bail when
  there was no previous type, which is exactly the first selection. Editing
  still never rewrites a saved placement.

- fix(catalog UI): the currency was rendered as a leading adornment, where the
  three-letter code MXN overlapped the amount; `useCurrency().symbol` says in
  its own comment that it is meant for suffixes. And the VAT select printed
  "General (16%) (16%)" — the seeded name already spells the rate out, so the
  label no longer appends it a second time.

- feat(catalog API): `specialty_ids` on item create/update. Assignment was
  only possible from the specialty side (`PUT /specialties/{id}/items`), which
  is a full replace and needs `catalog.admin` — unusable from an item form
  gated by `catalog.write`. Ids are resolved against the caller's clinic; an
  unknown one is a 400, not a 500.

- feat(catalog API): `/specialties` returns each specialty's `key`. The UI
  needs to match a specialty by meaning (`cirugia`) rather than by a display
  name the clinic may rename.

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
