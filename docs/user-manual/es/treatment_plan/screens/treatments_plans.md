---
module: treatment_plan
screen: treatments_plans
route: /treatments/plans
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
  - backend/app/modules/treatment_plan/frontend/pages/treatments/plans/index.vue
  - backend/app/modules/treatment_plan/router.py
last_verified_commit: 3568519
---

# Bandeja de planes

Bandeja de planes de tratamiento de la clínica. Se organiza en
**siete pestañas**: seis colas de seguimiento servidas por
`GET /pipeline` y un *Listado* final con todos los planes.

## De un vistazo

- **En curso** *(primera pestaña, la que se abre por defecto)*. Todo
  plan en marcha, sin importar en qué punto del circuito esté:
  `pending` (el doctor lo confirmó y espera al paciente) y `active`
  (presupuesto aceptado, tratamiento en ejecución). Recepción los ve
  igual — el plan echa a andar cuando el paciente acude a la consulta
  de diagnóstico, mucho antes de que se firme el presupuesto — así que
  repartirlos entre pestañas escondía trabajo que estaba vivo. Ordena
  por movimiento más reciente primero: responde «qué hay en marcha
  ahora», no es una cola que haya que vaciar.
- **Colas de acción.** *Por presupuestar* (confirmado, presupuesto en
  borrador), *Esperando paciente* (presupuesto enviado o caducado),
  *Sin cita* y *Sin próxima cita* (activos con tratamientos
  pendientes y agenda vacía), *Cerrados* (últimos 90 días).
- **Filas que se adaptan a su ancho.** Cada tarjeta decide cómo colocarse
  midiéndose a sí misma, no a la ventana: en cuanto la tarjeta baja de 56rem
  —tablet en vertical, con o sin raíl— el paciente pasa arriba y
  *Tratamientos*, *Presupuesto* y *días en estado* se reparten en una línea
  debajo. No se oculta nada; antes esas columnas se solapaban con el número
  de plan.
- **Cuándo se pone «En tratamiento».** El plan pasa a *En tratamiento*
  (`active`) por dos caminos, y basta con uno: cuando se **acepta el
  presupuesto**, o cuando el paciente **acude a la primera consulta** ligada
  al plan. La consulta cuenta aunque no se marque ningún tratamiento como
  ejecutado — una primera visita de diagnóstico rara vez marca alguno. Un
  plan en *Borrador* no se activa por asistir: primero hay que confirmarlo.
- **Aceptar en clínica.** Cuando el paciente dice que sí estando delante,
  el botón de la fila abre un diálogo que recoge su nombre y, si quieres,
  su firma manuscrita en la tablet. Aparece solo cuando el presupuesto
  está en *borrador* o *enviado*. Queda registrada una firma real —nombre,
  trazo, IP, fecha y método—, y aceptar el presupuesto arrastra el plan a
  *En tratamiento* por el camino de siempre.
- **Buscar por nombre.** El cuadro acepta el número de plan o el nombre del
  paciente, en cualquier orden y con o sin acentos: «Juan Pérez», «Pérez
  Juan» y «juan perez» llegan al mismo sitio. Cada palabra tiene que casar
  con algo, así que añadir una segunda acota en vez de ampliar.
- **Todos** *(última pestaña)*. Todos los planes de la clínica
  ordenados por fecha de creación, del más reciente al más antiguo,
  con filtro por estado. Es la vista de catálogo: aquí aparece
  cualquier plan, incluidos borradores y archivados que no entran en
  ninguna cola.
- **Los borradores sólo viven aquí.** La pestaña *Clínico* de la ficha
  del paciente no los lista: esa vista responde a «en qué punto está el
  tratamiento de este paciente», y un plan a medio escribir no es una
  respuesta — además empujaba hacia abajo los planes que sí importan.
  Se siguen viendo, editando y borrando desde *Todos*, cuyo filtro por
  estado incluye *Borrador*. Los planes anteriores sí siguen en la ficha,
  plegados al final de la lista bajo **Planes anteriores**: completados y
  cerrados van juntos, porque para quien lee el historial son la misma
  cosa —tratamiento terminado— y separarlos dejaba el pasado del paciente
  detrás de dos paneles distintos. La etiqueta de cada tarjeta sigue
  diciendo cuál de los dos es.
- **Paginación del pipeline.** Las columnas paginan de verdad: el
   paginador ignoraba los clics porque usaba la API antigua del
   componente, así que solo se veía la primera página.
- **Búsqueda y filtros.** Buscar por paciente o número de plan;
  filtros por profesional asignado, fecha de creación y motivo de
  cierre.
- **Sincronización con presupuesto.** Cada plan tiene un
  presupuesto enlazado (o lo crea al confirmar). Los cambios en el
  plan se propagan al presupuesto por eventos snapshot — no hace
  falta editar el presupuesto a mano.
- **Notas clínicas.** Desde el issue #60, las notas no se guardan
  en el plan: se delegan al módulo `clinical_notes`. El plan solo
  registra ejecuciones.

## Encontrar un plan

1. Cambia de pestaña o entra a la pipeline.
2. Filtra por profesional, fecha o motivo de cierre si procede.
3. Pulsa una fila para abrir el [detalle](./treatments_plans_id.md).

## Crear un plan

> Requiere `treatment_plan.plans.write`.

1. Pulsa **Nuevo plan** (top derecha) → te lleva a
   `/treatments/plans/new`.
2. Selecciona paciente, profesional y añade tratamientos.

## Registrar un contacto

> Requiere `treatment_plan.plans.write`.

1. En la fila o en el detalle, usa **Registrar contacto** para
   anotar una llamada / WhatsApp / email a recepción.
2. Estos contactos alimentan la vista de pipeline para no perder
   planes que llevan demasiado tiempo sin actividad.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver bandeja, pipeline y detalle | `treatment_plan.plans.read` |
| Crear, editar, añadir ítems, registrar contactos | `treatment_plan.plans.write` |
| Confirmar (borrador → pendiente) | `treatment_plan.plans.confirm` |
| Cerrar un plan | `treatment_plan.plans.close` |
| Reactivar un plan cerrado | `treatment_plan.plans.reactivate` |

## Resolución de problemas

- **El plan está en pendiente pero el paciente ya aceptó.** El
  evento `budget.accepted` lo mueve a *activo* automáticamente. Si
  no lo ha hecho, comprueba que el presupuesto está realmente
  aceptado y que ambos módulos están instalados.
- **No encuentro un plan cerrado.** En la pestaña *Cerrados* filtra
  por *motivo de cierre*. Por defecto incluye todos.
- **No aparece el botón *Confirmar*.** Tu rol no tiene
  `treatment_plan.plans.confirm` o el plan ya está en pendiente o
  posterior.
