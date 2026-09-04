---
module: treatment_plan
screen: treatments_plans_id
route: /treatments/plans/[id]
related_endpoints:
  - DELETE /api/v1/treatment_plan/treatments/plans/{plan_id}
  - DELETE /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatments/plans
  - GET /api/v1/treatment_plan/treatments/plans/patient/{patient_id}
  - GET /api/v1/treatment_plan/treatments/plans/pipeline
  - GET /api/v1/treatment_plan/treatments/plans/{plan_id}
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/items/reorder
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}/complete
  - PATCH /api/v1/treatment_plan/treatments/plans/{plan_id}/status
  - POST /api/v1/treatment_plan/treatments/plans
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/close
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/apply-template
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/confirm
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/contact-log
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/items
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/link-budget
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/reactivate
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/reopen
  - POST /api/v1/treatment_plan/treatments/plans/{plan_id}/sync-budget
  - PUT /api/v1/treatment_plan/treatments/plans/{plan_id}
  - PUT /api/v1/treatment_plan/treatments/plans/{plan_id}/items/{item_id}
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
  - treatment_plan.plans.confirm
  - treatment_plan.plans.close
  - treatment_plan.plans.reactivate
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/[id].vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanDetailView.vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanTreatmentList.vue
  - backend/app/modules/treatment_plan/proposals.py
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: e372dd4
---

# Detalle del plan de tratamiento

Vista del plan: cabecera con paciente, profesional y estado;
columna principal con los ítems (catálogo o tratamiento odontograma)
y columna lateral con presupuesto enlazado, ejecuciones y contactos.
Aquí se confirma, sincroniza con el presupuesto, marca ítems como
ejecutados y se cierra o reactiva.

## Construir el plan

Hay tres formas de meter tratamientos en un plan en borrador, y se
combinan:

- **Aplicar plantilla.** Trae una forma completa de plan (ver
  [Nuevo plan](./treatments_plans_new.md)). Se puede aplicar varias
  veces, así que un plan puede ser fase higiénica + implante
  unitario.
- **Proponer desde el odontograma.** El botón aparece con un número
  cuando el paciente tiene hallazgos marcados en la ficha para los que
  no hay nada planificado. La lista empareja cada hallazgo con el
  tratamiento que le corresponde — caries → obturación, pulpitis en
  molar → endodoncia molar — y con **Añadir** entran todos. El
  hallazgo se queda en el odontograma: el diagnóstico y el plan son
  cosas distintas y la caries sigue ahí hasta que se trate.
  Desmarca la fila si la propuesta no encaja y añádelo a mano desde
  la barra.
- **Barra de tratamientos.** Elige el tratamiento y haz clic en el
  diente. El tratamiento **sigue armado** después de aplicarlo, así
  que 16, 26 y 36 son tres clics, no tres búsquedas. La chapa de la
  cabecera dice qué está armado; la ✕ o `Esc` lo sueltan. Para un
  cuadrante entero, usa los botones **Cuadrante 1–4** que aparecen
  junto a la chapa: pide confirmación nombrando las piezas antes de
  crear nada.

La lista del plan se agrupa por **fase**: urgencia, estabilización,
rehabilitación, mantenimiento. La fase de cada partida sale del
catálogo. Arrastrar reordena dentro de una fase; para mover algo a
otra fase, cambia la fase del tratamiento.

**Guardar como plantilla** está en el menú **···**: se guardan los
tratamientos y sus fases, no los dientes ni los precios.

## De un vistazo

- **Estado y chip.** El chip en la cabecera refleja el estado:
  `draft`, `pending`, `active`, `completed`, `closed`. Las acciones
  cambian según el estado.
- **Ítems** — añadir, reordenar, completar. Cada ítem referencia un
  ítem del catálogo y, opcionalmente, un tratamiento del odontograma.
  Al completar un ítem se publica
  `treatment_plan.treatment_completed` (con `treatment_category_key`
  para recalls).
- **Doctor por tratamiento.** Cada ítem lleva su propio
  `assigned_professional_id`. Los nuevos ítems heredan el doctor del
  plan. Pulsa el chip de color junto al nombre del tratamiento para
  asignar a otro profesional (p. ej. empaste por Dr. A, endodoncia
  por Dr. B). Cuando intervienen dos o más doctores en el plan, el
  color del chip deja visible la mezcla de un vistazo. El chip
  sigue editable mientras el ítem esté pendiente, incluso después
  de validar el plan y de que el presupuesto esté activo —
  reasignar es operativo y no cambia el acuerdo con el paciente.
  Al completarlo, el chip pasa a ser un indicador de solo lectura
  que sigue mostrando `assigned_professional_id` (el doctor
  responsable del tratamiento); marcarlo como completado puede
  hacerlo recepción o un admin en nombre del clínico, así que
  "quién pulsó Completar" no es la referencia del chart.
- **Presupuesto enlazado.** Botones **Generar presupuesto** /
  **Enlazar con presupuesto existente** / **Sincronizar** según el
  caso. El plan publica `treatment_plan.treatment_added /
  _removed / budget_sync_requested` para que `budget` mantenga el
  presupuesto al día.
- **Contactos** — historial de toques de recepción. Útil cuando el
  plan está en *pendiente* esperando aceptación.
- **Notas clínicas.** Pueden engancharse al plan desde el módulo
  `clinical_notes` (slot `patient.detail.clinical.notes`).

## Confirmar un plan

> Requiere `treatment_plan.plans.confirm`.

1. Sobre un plan en `draft`, pulsa **Confirmar**.
2. Se publica `treatment_plan.confirmed`. El plan pasa a `pending`.
3. Si no había presupuesto enlazado, **Generar presupuesto** crea
   uno nuevo en el módulo `budget`.

## Marcar ítems como ejecutados

> Requiere `treatment_plan.plans.write`.

1. En el ítem, pulsa **Marcar como hecho**.
2. Se publica `treatment_plan.treatment_completed`. `recalls` puede
   sugerir un próximo recall basado en `treatment_category_key`.
3. Para anotar una nota clínica en ese momento, usa el botón de
   *Añadir nota* (lo aporta `clinical_notes`).

**Quitar un ítem del plan** (icono de papelera en la fila) pide
confirmación: la baja arrastra el tratamiento del odontograma y la
línea de presupuesto asociada.

## Tratamientos en varias sesiones

Algunos tratamientos del catálogo (p.ej. corona, endodoncia) tienen
una **plantilla de sesiones** con nombre e importe por paso. Al
añadirlos al plan se crea automáticamente una sesión por cada paso.

- El item muestra un chip **X/Y sesiones** con el progreso.
- Bajo el item aparece la lista de sesiones (icono ✓ por completada,
  círculo punteado por pendiente).
- Pulsa el check de cada sesión para marcarla realizada — publica
  `treatment_plan.item_session_completed` y `payments` registra una
  entrada de "trabajo realizado" por ese importe.
- El item se finaliza automáticamente al completar la última sesión
  pendiente (entonces se ejecuta el flujo legacy de cierre).
- Cancela una sesión si no llegó a hacerse: no genera cobro.

## Cambiar el doctor del plan

> Requiere `treatment_plan.plans.write`.

1. Abre **Editar plan** y selecciona otro profesional.
2. Si hay tratamientos pendientes asignados al doctor anterior,
   aparece un confirm: *"¿Reasignar los tratamientos pendientes?"*.
3. Pulsa **Sí, reasignar pendientes** para mover todos los ítems
   pendientes que coincidían con el doctor anterior al nuevo en el
   mismo guardado. Los ítems con override explícito (otro doctor)
   y los completados no se tocan nunca.
4. Pulsa **No, dejar como están** si solo quieres cambiar el
   doctor del plan; los ítems mantienen su asignación.

## Cerrar o reactivar

> Cerrar requiere `treatment_plan.plans.close`. Reactivar requiere
> `treatment_plan.plans.reactivate`.

1. **Cerrar** — elige motivo: rechazado, expirado, cancelado,
   abandono u *otro*. Publica `treatment_plan.closed` con
   `closure_reason`.
2. **Reactivar** — vuelve al estado `draft`. Publica
   `treatment_plan.reactivated`.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver detalle, ítems y contactos | `treatment_plan.plans.read` |
| Añadir/reordenar ítems, completarlos, registrar contactos | `treatment_plan.plans.write` |
| Confirmar (draft → pending) | `treatment_plan.plans.confirm` |
| Cerrar | `treatment_plan.plans.close` |
| Reactivar | `treatment_plan.plans.reactivate` |

## Resolución de problemas

- **Confirmé el plan pero el presupuesto no aparece.** Pulsa
  **Generar presupuesto** o **Enlazar con presupuesto existente**.
  Confirmar no crea automáticamente el presupuesto a menos que se
  use *Generar* después.
- **El paciente aceptó el presupuesto pero el plan sigue en
  pendiente.** Comprueba que el evento `budget.accepted` está
  fluyendo (el módulo `budget` ha de estar instalado y el
  presupuesto realmente aceptado). El handler
  `on_budget_accepted` lo mueve a *activo*.
- **No puedo borrar un ítem.** El ítem ya está marcado como hecho.
  Los ítems completados quedan como histórico.
- **No me deja completar un ítem.** Tu rol no tiene
  `treatment_plan.plans.write`.
