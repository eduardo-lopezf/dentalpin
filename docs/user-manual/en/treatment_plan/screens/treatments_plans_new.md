---
module: treatment_plan
screen: treatments_plans_new
route: /treatments/plans/new
related_endpoints:
  - POST /api/v1/treatment_plan/treatments/plans
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/catalog-items
  - GET /api/v1/treatment_plan/plan-templates
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/new.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanDraftChart.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanTreatmentSearch.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanDraftLines.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: e372dd4
---

# New treatment plan

Drawn first, signed afterwards. The screen opens on a blank dental chart:
you tap a tooth, say what it needs, and only once the plan is on screen
does it ask whose mouth it was. On save the plan is born in `draft` and
the [detail](./treatments_plans_id.md) opens so you can confirm it and
generate a budget.

## At a glance

- **Two steps, in this order.** The chart and the treatments first; the
  patient, title, professional and notes after. It is the order someone
  who has just looked in a mouth actually works in.
- **The chart is blank.** There is no patient yet, so there is no history
  to draw: what you see is the plan you are making, not what the patient
  has. **Nothing stops you planning on a missing tooth** — the next step
  is what warns about that.
- **Nothing is saved until *Create*.** The patient (if new), the plan and
  every line are written in one go at the end. A half-built plan you
  walk away from leaves nothing behind.
- **From the patient record** (*Clinical → Plans → New plan*) you land on
  this same screen with the patient already filled in and the title
  already written. The chart still comes first.
- **Whole mouth.** Treatments that do not hang off a tooth — a cleaning,
  a panoramic, a first consultation — are added through the *Whole mouth*
  button, not by tapping a tooth.

## Step 1 — Draw the plan

> Requires `treatment_plan.plans.write`.

1. Tap a tooth (or one face, for a per-surface treatment). A side panel
   opens, titled with the tooth.
2. **Before you type anything** the panel already offers *Recently
   used*: what your clinic has been doing lately, which is usually the
   answer. Not "most used ever" — recency, because a practice repeats
   this week's work.
3. Typing searches two places at once: your **templates** and the
   **catalog**. Accents are ignored, and templates also match on what
   they contain, so "implant" finds the template even when its name never
   says so.
4. Picking a treatment adds it to that tooth. Picking a **template** adds
   all of its lines at once: the per-tooth ones land on the tooth you
   were on, the whole-mouth ones ask for none.
5. The list on the right (below, when held upright) is the plan. The
   pencil opens that line's phase and note; the bin removes it. The total
   keeps itself up to date.
6. **Continue** once there is at least one treatment.

## Step 2 — Whose mouth it was

1. Search the patient by name or phone, or press **Create a new patient**
   and type first name, last name and phone. The patient is created when
   you press *Create*, not before.
2. Choosing them makes the screen read their real chart and **flag what
   clashes**: a tooth recorded as missing, or the same treatment already
   planned on that tooth. It is a warning, not a block — you can **Fix it
   on the chart** or carry on.
3. The **title** writes itself as *Treatment Plan for [name]* and stays
   editable. Once you touch it, it stops rewriting itself.
4. Assign the professional. It is pre-selected when your user is a clinic
   professional.
5. Diagnosis and internal notes live under **More options**.
6. **Create**. `treatment_plan.created` is published, every line is added
   and you land on the detail with the plan built.

> If a treatment is no longer in your catalog, that line is skipped and
> the notice names it. The rest of the plan is created.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| Reach the form and see templates and catalog | `treatment_plan.plans.read` |
| Create the plan and add its treatments | `treatment_plan.plans.write` |
| Create, edit or hide templates | `treatment_plan.plans.templates` |

## Troubleshooting

- **"Recently used" is empty.** The list fills from what the clinic
  records; on a brand-new clinic it is empty and the panel says so.
  Search the catalog meanwhile.
- **A treatment does not show up.** The search needs two letters and only
  offers active treatments. Findings (caries, fracture) are not planned
  here: they are charted on the patient's odontogram.
- **I tapped a tooth and the treatment did not land on it.** Whole-mouth
  and whole-arch treatments do not hang off a tooth even when picked from
  one; they appear in the list as *Whole mouth*.
- **"Whole mouth" will not let me pick a treatment.** Per-tooth ones are
  dimmed there, because there would be no tooth to put them on. Pick
  those from the tooth.
- **The tooth warning never appears.** It can only appear after a patient
  is chosen, and it needs permission to read the odontogram. Without it
  the plan is still created, just unchecked.
- **Empty professional picker.** If your role is admin or front desk and
  no professionals show up, create or activate them under *Settings →
  Users*.
