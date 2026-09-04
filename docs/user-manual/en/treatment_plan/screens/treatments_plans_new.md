---
module: treatment_plan
screen: treatments_plans_new
route: /treatments/plans/new
related_endpoints:
  - GET /api/v1/treatment_plan/treatments/plans
  - GET /api/v1/treatment_plan/treatments/plans/patient/{patient_id}
  - POST /api/v1/treatment_plan/treatments/plans
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/items
  - GET /api/v1/treatment_plan/plan-templates
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/apply-template
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/link-budget
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/new.vue
  - backend/app/modules/treatment_plan/frontend/components/treatment-plans/PlanTemplatePicker.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: e372dd4
---

# New treatment plan

Form to create a treatment plan for a patient. On save, the plan is
born in `draft` and the [detail](./treatments_plans_id.md) opens so
you can add items, confirm, and generate a budget.

## At a glance

- **How you get here.** Usually from the patient record (patient
  pre-selected) or from the inbox via **New plan**.
- **Assigned professional.** Front desk can assign a professional;
  a non-admin professional can only assign themselves.
- **Template.** The form asks which shape of plan to start from.
  This is the decision that saves the work: picking *Endodontics +
  build-up + crown* and naming the tooth leaves the plan with its four
  treatments already in place and staged. **Blank** creates an empty
  plan to build from the chart.
- **Teeth.** Asked for only when the template needs them. Each
  per-tooth treatment is added once for every tooth you list, so
  *Third molar extraction* with `18, 28, 38, 48` gives you all four.
  Whole-mouth templates (first visit, hygiene phase) ask for nothing.
- **Budget.** Not created here. After creating the plan, on the
  detail click **Generate budget** or **Link to existing budget**.

## Create a plan

> Requires `treatment_plan.plans.write`.

1. Pick the patient (if not pre-selected).
2. Choose the template, or **Blank** to build the plan from the
   chart. The treatments it carries are listed under the cards,
   flagging which ones are waiting for a tooth.
3. If the template asks for them, type the teeth in FDI notation
   separated by commas or spaces (`16, 26, 36, 46`). Until there is
   at least one, **Create** says which treatments are waiting.
4. The professional is pre-selected when your user is a clinic
   professional. The template names the plan; change that, and the
   notes, under **More options**.
5. **Create**. `treatment_plan.created` is published, the template is
   applied, and you land on the detail with the plan already built.

> If applying the template fails, the plan is still created, empty:
> that is a valid starting point and you can apply the template again
> from the detail.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| Access the form and see the catalog | `treatment_plan.plans.read` |
| Create the plan and apply a template | `treatment_plan.plans.write` |
| Create, edit or hide templates | `treatment_plan.plans.templates` |

## Troubleshooting

- **Empty professional picker.** When you can only assign yourself,
  the picker is pinned to your user. If your role is admin / front
  desk and no professionals show up, create or activate them under
  *Settings → Users*.
- **Cannot add a treatment from the odontogram.** The patient has
  no planned treatments visible. Create one from the patient's
  Clinical tab before planning it.
- **No templates show up.** Templates are installed when the clinic
  is created. On a clinic that predates this feature, run
  `docker-compose exec backend python scripts/backfill_plan_templates.py`.
- **"16, 26" is rejected.** Only FDI notation is accepted: 11–48
  permanent, 51–85 deciduous. The warning names the value that
  fails.
