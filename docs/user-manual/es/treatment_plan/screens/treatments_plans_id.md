---
module: treatment_plan
screen: treatments_plans_id
route: /treatments/plans/[id]
related_endpoints:
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}
  - DELETE /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatment-plans
  - GET /api/v1/treatment_plan/treatment-plans/patient/{patient_id}
  - GET /api/v1/treatment_plan/treatment-plans/pipeline
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/reorder
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/complete
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/reopen
  - PATCH /api/v1/treatment_plan/treatment-plans/{plan_id}/status
  - POST /api/v1/treatment_plan/treatment-plans
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/close
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/apply-template
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/proposals
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/confirm
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/contact-log
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/generate-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/items
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/link-budget
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reactivate
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/reopen
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/sync-budget
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}
  - PUT /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}
  - GET /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/prescriptions
  - POST /api/v1/treatment_plan/treatment-plans/{plan_id}/items/{item_id}/prescriptions
  - GET /api/v1/treatment_plan/prescriptions/{prescription_id}/pdf
related_permissions:
  - treatment_plan.plans.read
  - treatment_plan.plans.write
  - treatment_plan.plans.confirm
  - treatment_plan.plans.close
  - treatment_plan.plans.reactivate
  - treatment_plan.prescriptions.read
  - treatment_plan.prescriptions.write
related_paths:
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/[id].vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanDetailView.vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/PlanTreatmentList.vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/modals/PlanItemDetailModal.vue
  - backend/app/modules/treatment_plan/frontend/components/clinical/modals/PlanItemPrescriptionModal.vue
  - backend/app/modules/treatment_plan/prescriptions.py
  - backend/app/modules/treatment_plan/proposals.py
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 2b664a5
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
  unitario. La ventana lleva un buscador que filtra las plantillas por
  nombre y por los tratamientos que llevan dentro; aquí no ofrece
  tratamientos sueltos, porque para eso ya está el odontograma.
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

## Calendario de pagos

La tarjeta **Calendario de pagos** guarda lo que se pactó cobrar y
cuándo, que es una pregunta distinta de «qué se debe por trabajo
hecho» — esa la responde la tarjeta de cobros. En un caso grande el
dinero se pacta por adelantado, así que es normal que una diga 0 y la
otra vaya al día. **No se suman**: las dos se saldan contra los mismos
pagos.

**Pactar calendario** propone tres repartos del total del plan: por
fases (cada fase, su precio), 30/40/30 y mensual. A partir de ahí cada
plazo lleva su **etiqueta**, su **fecha** y su **importe**, los tres
editables: el reparto sólo escribe el primer borrador. Así se pactan
cosas como «5.000 a la firma y el resto en seis mensualidades» — elige
el reparto mensual con siete plazos y ajusta los importes.

Los plazos tienen que sumar el total del plan; mientras no cuadren, el
aviso dice cuánto suman y el botón de guardar no deja continuar. La fecha puede quedarse en blanco — un hito
como «antes de la cirugía» no tiene fecha hasta que se agenda, y sin
fecha nunca aparece como vencido.

Los plazos se cubren en orden con lo que el paciente va pagando, y cada
uno muestra **Pendiente**, **Parcial**, **Pagado** o **Vencido**.

**Editar** (el lápiz) abre el calendario tal como se pactó, no un
reparto nuevo. Cada fila se puede quitar, o añadir otra justo debajo —
que es lo que hace falta para partir un plazo en dos cuando el paciente
no puede con uno. Se puede renegociar aunque ya se haya cobrado: lo
pagado vuelve a cubrir los plazos nuevos en orden.

Anular un calendario no lo borra: un acuerdo superado es parte de lo que
pasó.

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
- **Ficha del tratamiento.** Toca el recuadro de un tratamiento y se
  abre su ventana: profesional, precio, dientes, sesiones y el estado
  del dinero (ejecutado, cobrado, pendiente). Al pie, como botones
  azules del mismo tamaño, están **Añadir nota** (o **Notas (n)** si ya
  tiene), **Programar recordatorio**, **Cobrar** (solo si queda algo
  pendiente) y **Receta médica**; en la última casilla, **Marcar como
  completado** en verde, o **Reabrir tratamiento** si ya está hecho. La
  fila se queda solo con lo que cambia el plan
  (completar, quitar), que es lo que evita confundir «abrir algo» con
  «cambiar el plan» a un dedo de distancia.

## Confirmar un plan

> Requiere `treatment_plan.plans.confirm`.

1. Sobre un plan en `draft`, pulsa **Confirmar**.
2. Se publica `treatment_plan.confirmed`. El plan pasa a `pending`.
3. Si no había presupuesto enlazado, **Generar presupuesto** crea
   uno nuevo en el módulo `budget`.

## Marcar ítems como ejecutados

> Requiere `treatment_plan.plans.write`.

1. En el ítem, pulsa el ✓ de la fila o **Marcar como completado**
   dentro de su ventana.
2. Se publica `treatment_plan.treatment_completed`. `recalls` puede
   sugerir un próximo recall basado en `treatment_category_key`.
3. Acto seguido la aplicación pregunta **si cobras ahora o lo dejas
   pendiente**. Es el momento más barato para cobrar —el paciente
   sigue en el sillón— pero *dejar pendiente* es una respuesta tan
   válida como la otra: una clínica que factura a fin de mes lo hace
   todos los días, y el importe queda igualmente en «pendiente de
   cobrar».
4. Para anotar una nota clínica, ábrela desde la ventana del
   tratamiento (**Añadir nota**, lo aporta `clinical_notes`).

**Quitar un ítem del plan** (icono de papelera en la fila) pide
confirmación: la baja arrastra el tratamiento del odontograma y la
línea de presupuesto asociada.

## Receta médica

> Escribir una receta requiere `treatment_plan.prescriptions.write`
> (administrador y dentista). Verlas y reimprimirlas,
> `treatment_plan.prescriptions.read` (también higienista, auxiliar y
> recepción).

1. En la ventana del tratamiento pulsa **Receta médica**.
2. **Doctor que firma** viene con el profesional asignado al
   tratamiento; puedes elegir otro del directorio. Debajo se ve su
   **cédula profesional**, o un aviso si no la tiene registrada (la
   receta saldría sin ella: complétala en el menú *Profesionales*).
3. Escribe las **indicaciones**: medicamento, dosis, frecuencia y
   duración.
4. Pulsa **Generar receta**. Se abre una pestaña con el PDF listo para
   imprimir: datos de la clínica (nombre, dirección, teléfono, correo),
   nombre y cédula del doctor, paciente, edad, fecha, tratamiento, las
   indicaciones y la línea de firma.

La receta **queda guardada** en el expediente y aparece en *Recetas
anteriores* con su botón **Imprimir**. El nombre y la cédula del doctor
se copian al generarla: si mañana cambian en el directorio, la
reimpresión sigue diciendo lo que llevó el paciente a la farmacia. Si
quitas el tratamiento del plan, la receta no se borra.

## Tratamiento cerrado, y cómo reabrirlo

Un tratamiento aparece como **Cerrado** cuando está completado **y** no
queda nada por cobrar de él. No es un estado que se guarde: se deduce
del dinero, así que no puede desincronizarse del libro. La **receta
médica** está disponible también con el tratamiento cerrado.

Si marcaste un tratamiento como hecho por error —esté cerrado o todavía
con cobro pendiente—, ábrelo y pulsa **Reabrir tratamiento**. La ventana
te explica qué va a pasar antes de hacerlo; al confirmar con **Sí,
reabrir**:

- El tratamiento **vuelve a pendiente** y deja de contar como hecho,
  también en el odontograma.
- **Se retira su cargo.** Ya no aparece como pendiente de cobro ni en el
  plan ni en la cuenta del paciente.
- **Lo que ya se cobró no se devuelve.** Queda como saldo a favor del
  paciente y cubrirá el tratamiento cuando lo completes de verdad. Si lo
  que quieres es devolver el dinero, eso se hace en Finanzas.
- Si el plan estaba **completado**, vuelve a **Activo**, porque
  ahora tiene trabajo pendiente.
- En un tratamiento de **varias sesiones** solo se reabre la última
  sesión que se completó; las anteriores siguen hechas y cobradas.
- Queda anotado en el **historial del plan** como *Tratamiento
  reabierto*.

No se puede reabrir un tratamiento de un plan **cerrado**: primero hay
que reactivar el plan.

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
| Ver y reimprimir recetas | `treatment_plan.prescriptions.read` |
| Escribir una receta | `treatment_plan.prescriptions.write` |

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
- **Hago clic en un diente y no pasa nada.** El plan está en curso: el
  odontograma se queda en **solo lectura** mientras haya un presupuesto
  vivo. Al hacer clic sale un aviso con el botón **Reabrir**, que
  devuelve el plan a borrador cancelando ese presupuesto — el mismo
  botón de la cabecera, y pide confirmación antes de nada. Si el aviso
  no ofrece ese botón es porque reabrir es cosa de un administrador o de
  un profesional asignado al caso, o porque el plan ya está completado o
  cerrado.
