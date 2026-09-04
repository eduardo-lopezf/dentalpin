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

# Nuevo plan de tratamiento

Formulario para crear un plan de tratamiento para un paciente. Al
guardar, el plan nace en estado `draft` y se abre el
[detalle](./treatments_plans_id.md) para añadir ítems, confirmar y
generar presupuesto.

## De un vistazo

- **Origen.** Suele llegarse desde la ficha del paciente (paciente
  preseleccionado) o desde la bandeja con **Nuevo plan**.
- **Profesional asignado.** Recepción puede asignar al profesional;
  un profesional sin permiso de admin solo puede asignarse a sí
  mismo.
- **Plantilla.** El formulario pregunta desde qué forma de plan
  empezar. Es la decisión que ahorra trabajo: elegir *Endodoncia +
  reconstrucción + corona* e indicar la pieza deja el plan con sus
  cuatro tratamientos ya puestos y en su fase. **En blanco** crea el
  plan vacío para construirlo desde el odontograma.
- **Dientes.** Solo se piden cuando la plantilla los necesita. Cada
  tratamiento por diente se añade una vez por cada pieza que indiques,
  así que *Extracción de cordales* con `18, 28, 38, 48` deja las cuatro
  extracciones. Las plantillas de boca completa (primera visita, fase
  higiénica) no piden nada.
- **Presupuesto.** No se crea aquí. Tras crear el plan, en el
  detalle pulsas **Generar presupuesto** o **Enlazar con presupuesto
  existente**.

## Crear un plan

> Requiere `treatment_plan.plans.write`.

1. Selecciona paciente (si no viene preseleccionado).
2. Elige la plantilla, o **En blanco** si prefieres construir el plan
   desde el odontograma. Bajo las tarjetas se listan los tratamientos
   que trae, marcando cuáles esperan pieza.
3. Si la plantilla los pide, escribe los dientes en notación FDI
   separados por comas o espacios (`16, 26, 36, 46`). Hasta que no
   haya al menos uno, el botón **Crear** dice qué tratamientos están
   esperando.
4. El profesional viene preseleccionado si tu usuario es un
   profesional de la clínica. El título lo pone la plantilla; puedes
   cambiarlo, junto con las notas, en **Más opciones**.
5. **Crear**. Se publica `treatment_plan.created`, se aplica la
   plantilla y entras al detalle con el plan ya montado.

> Si la plantilla se queda a medias, el plan se crea igualmente y
> vacío: es un punto de partida válido y puedes aplicarla de nuevo
> desde el detalle.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Acceder al formulario y ver el catálogo | `treatment_plan.plans.read` |
| Crear el plan y aplicar una plantilla | `treatment_plan.plans.write` |
| Crear, editar u ocultar plantillas | `treatment_plan.plans.templates` |

## Resolución de problemas

- **Selector de profesional vacío.** Cuando solo puedes asignarte a
  ti, el selector queda fijado a tu usuario. Si tu rol es admin/
  recepción y no salen profesionales, créalos o actívalos en
  *Ajustes → Usuarios*.
- **No me deja añadir un tratamiento del odontograma.** El paciente
  no tiene tratamientos planificados visibles. Crea uno desde la
  pestaña Clínica del paciente antes de planificarlo.
- **No aparece ninguna plantilla.** Las plantillas se instalan al
  crear la clínica. En una clínica anterior a esta función, ejecuta
  `docker-compose exec backend python scripts/backfill_plan_templates.py`.
- **«16, 26» no me lo acepta.** Solo se admite notación FDI: 11–48
  en permanente y 51–85 en temporal. El aviso indica el valor que
  falla.
