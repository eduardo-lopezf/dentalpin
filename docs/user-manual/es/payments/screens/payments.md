---
module: payments
screen: list
route: /payments
related_endpoints:
  - GET /api/v1/payments
  - GET /api/v1/payments/budgets/{budget_id}/allocations
  - GET /api/v1/payments/filters/budgets-by-status
  - GET /api/v1/payments/filters/patients-with-debt
  - GET /api/v1/payments/patients/{patient_id}/ledger
  - GET /api/v1/payments/receivables
  - GET /api/v1/payments/receivables/{patient_id}/contacts
  - POST /api/v1/payments/receivables/{patient_id}/contacts
  - GET /api/v1/cashbox/periods
  - GET /api/v1/payments/reports/aging-receivables
  - GET /api/v1/payments/reports/by-method
  - GET /api/v1/payments/reports/by-professional
  - GET /api/v1/payments/reports/refunds
  - GET /api/v1/payments/reports/summary
  - GET /api/v1/payments/reports/trends
  - GET /api/v1/payments/{payment_id}
  - GET /api/v1/payments/{payment_id}/refunds
  - POST /api/v1/payments
  - POST /api/v1/payments/summary/by-budgets
  - POST /api/v1/payments/summary/by-patients
  - POST /api/v1/payments/{payment_id}/reallocate
  - POST /api/v1/payments/{payment_id}/refunds
related_permissions:
  - payments.record.read
  - payments.record.write
  - payments.record.refund
  - payments.reports.read
related_paths:
  - backend/app/modules/payments/frontend/pages/payments/index.vue
  - backend/app/modules/payments/router.py
last_verified_commit: 75cd119
---

# Listado de cobros


> **Dónde está.** Esta pantalla es la pestaña **Cobros** de
> **Finanzas**, en el menú lateral justo después de Profesionales.
> La antigua dirección `/payments` sigue funcionando y redirige aquí.

Caja operativa de la clínica. Cada fila es un cobro recibido del
paciente, con su importe bruto, las asignaciones a presupuestos o
*a cuenta*, y el importe reembolsado si lo hay. Desde aquí se
registra un cobro nuevo, se reasigna o se emite un reembolso.

> **En tablet.** El listado conserva la disposición en filas tanto en
> horizontal como en vertical. Solo los teléfonos lo apilan en tarjetas,
> así que girar la tablet no reorganiza la información.


> **Al tocar una fila** se abre la ficha del cobro: importe, devuelto y
> neto, las asignaciones a presupuesto o *a cuenta*, el método, la fecha,
> la referencia y quién lo registró. Desde ahí también se puede devolver.

## De un vistazo

- **Visión por paciente, no por factura.** Cada cobro pertenece a
  un paciente y se distribuye en *allocations* (presupuesto o
  *on_account*). La factura sale por otro flujo en `billing` y enlaza
  con estos cobros, nunca al revés.
- **Filtros activos en la URL** — método, paciente, rango de fechas,
  *Con reembolsos*, *Con saldo a cuenta*. Compartir el enlace
  comparte los filtros.
- **Orden:** por defecto por fecha de cobro descendente. Disponible
  también por importe.
- **Off-books.** El listado nunca cruza *cobrado* contra
  *facturado* — esa comparación es una decisión deliberada del
  producto (ver ADR 0010).
- **Estado de reembolso:** si el cobro tiene reembolsos, ves en rojo
  la cantidad reembolsada bajo el importe. El botón ↺ solo aparece
  cuando queda saldo neto y tu rol puede reembolsar.

## El Resumen de Finanzas

> Finanzas → **Resumen**, la primera pestaña y la que se abre por defecto.

Finanzas eran seis registros —Cobros, Por cobrar, Caja, Presupuestos,
Facturas, Liquidaciones—. Todos son buenas listas y **ninguno responde la
pregunta con la que se entra**: *¿cómo voy?* La respuesta existía, en
**Informes**, que es otra entrada del menú; quien quiere ver «el dinero»
abre Finanzas y encuentra listas.

Ahora lo primero es la respuesta, y los registros quedan a un clic:

| Ficha | Dice | De dónde sale |
|---|---|---|
| **Cobrado** | lo que entró hoy, neto de devoluciones, y el acumulado del mes | `payments` |
| **Por cobrar** | trabajo hecho y sin cobrar, con cuántos pacientes y cuánto lleva más de 90 días, y un botón a la bandeja | `payments` |
| **Caja** | días sin arquear de la quincena, con acceso al arqueo | `cashbox` |

Cada ficha la pone **su propio módulo**. Una clínica sin `cashbox` no ve la
ficha de caja y la fila se cierra sola; un perfil que puede trabajar las
listas pero no leer los informes de dinero ve el resumen vacío y se le dice
por qué, en vez de un rectángulo en blanco.

La ficha de caja distingue tres cosas que no son la misma: **días sin
arquear** (lo que hay que hacer), **al día** (se contó y cuadra) y **sin
movimiento** (la quincena no ha visto dinero). La tercera importa: contar
cero días arqueados como «al día» le diría a una clínica que nunca ha hecho
un arqueo que va perfectamente.

## La bandeja «Por cobrar»

> Finanzas → **Por cobrar**. Requiere `payments.record.read`.

*Cobros* cuenta lo que entró. Esta pestaña cuenta **lo que no**, y es una
lista de personas, no una cifra.

Antes existía el dato pero no la lista: el informe decía «siete pacientes
deben 12.400 en el tramo de 90 días» y, al pulsar cualquiera de los cuatro
tramos, llevaba a *Pacientes con deuda* — el mismo sitio para los cuatro y
sin la antigüedad. Así que el número se miraba y de él no salía nada. Los
presupuestos tienen quien los persiga; el dinero ya ganado no tenía a nadie.

- **Ordenada por deuda más vieja primero**, que es el dinero en más riesgo
  y el orden en que una persona trabajaría.
- Cada fila trae lo que hace falta para llamar sin abrir la ficha: el
  **nombre**, **cuánto** debe, **cuántos días** lleva, y **cuándo pagó algo
  por última vez** — un paciente que pagó la semana pasada es otra
  conversación que uno callado desde marzo.
- Botones de **llamar**, **WhatsApp** y **Cobrar**. El cobro se abre ya con
  el paciente puesto y el importe sugerido.
- Los **cuatro tramos** (0-30, 31-60, 61-90, 90+) filtran, y el filtro va en
  la dirección: desde el informe de cobros, pulsar un tramo aterriza aquí
  ya filtrado por él.

**La antigüedad se mide desde el tratamiento que el dinero no alcanzó**, no
desde el más antiguo del paciente. La diferencia es lo que hace útil la
lista: alguien que lleva tres años viniendo y está al día salvo el empaste
de la semana pasada tiene su primer tratamiento en 2023, y contarlo desde
ahí lo metería en el tramo de 90+ junto a la morosidad de verdad. Una cola
equivocada con los mejores pacientes de la clínica no se abre dos veces.

### Anotar un contacto

El botón de la libreta guarda **que se intentó**: por dónde —llamada,
WhatsApp, correo, en persona u otro— y, si hace falta, una línea. Nada más:
en cuanto sea un formulario con campos obligatorios, recepción dejará de
rellenarlo después de una llamada que no dio nada, que es justo la llamada
que merece constar.

La fila lo enseña. Contactado hoy sale como distintivo, con el canal
(*contactado hoy (WhatsApp)*); un contacto más viejo solo lleva su fecha.
Es lo que evita que dos personas llamen al mismo paciente antes de comer.

**Un contacto no mueve dinero.** Es una nota sobre un intento; si el intento
funcionó, hay un cobro que lo demuestra. Separarlos es lo que permite que la
fila diga «contactado ayer, sigue debiendo 300».

El paciente **no desaparece** de la lista al contactarlo: sigue debiendo, y
esconderlo haría que la lista no cuadrase con el total de arriba.

## Registrar un cobro

> Requiere `payments.record.write`.

1. Pulsa **Nuevo cobro** en la cabecera (o desde la tarjeta de
   presupuesto en la ficha del paciente).
2. Elige el paciente. Selecciona método (efectivo, tarjeta,
   transferencia, débito, seguro u *otro*) y la fecha del cobro.
3. Reparte el importe entre los presupuestos abiertos del paciente,
   o déjalo *a cuenta* para asignarlo más tarde. La suma de
   asignaciones debe igualar el importe — el formulario valida el
   invariante antes de enviar.
4. **Guardar**. Se publican `payment.recorded` y un
   `payment.allocated` por cada asignación. La tarjeta lateral
   *Cobrado/Pendiente* del presupuesto se actualiza al instante.

## Reasignar un cobro

> Requiere `payments.record.write`.

1. Abre el cobro pulsando sobre su fila o desde la ficha del paciente.
2. Usa **Reasignar** para mover importe entre presupuestos o entre
   presupuesto y *a cuenta*. Cada cambio publica
   `payment.allocated` con el destino anterior y el nuevo.

## Reembolsar

> Requiere `payments.record.refund`. Por defecto solo admin y
> dentista. Un admin puede otorgarlo a recepción desde *Ajustes →
> Usuarios → Roles*.

1. Pulsa ↺ en la fila del cobro (solo visible si queda saldo neto).
2. Indica el importe (parcial o total) y el motivo. El reembolso
   nunca borra el cobro original: queda como una fila `Refund` y
   resta del *neto* en la cabecera.
3. **Confirmar**. Se publica `payment.refunded` y la fila muestra
   `− 50,00 €` bajo el importe bruto.

En el panel de cobros de la ficha del paciente, el menú **⋮** de cada
fila ofrece solo *Reembolsar*: no hay página de detalle de un cobro,
y la entrada que enlazaba a una se ha retirado — llevaba a un 404.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver listado, asignaciones, libro mayor del paciente | `payments.record.read` |
| Registrar un cobro y reasignarlo | `payments.record.write` |
| Emitir un reembolso | `payments.record.refund` |
| Acceder a los informes de cobros | `payments.reports.read` |

## Resolución de problemas

- **El listado está vacío con filtros activos.** Pulsa **Limpiar
  filtros** en la barra (chip con el contador). Si sigues sin ver
  cobros, comprueba el rango de fechas — por defecto no hay rango.
- **No me deja guardar el cobro: "suma de asignaciones no coincide".**
  El total de las *allocations* debe igualar el importe bruto. Ajusta
  un valor o añade una asignación *a cuenta* por la diferencia.
- **No veo el botón ↺ aunque mi rol debería poder reembolsar.** El
  cobro ya está reembolsado al 100% (el neto es 0). Solo se permite
  reembolsar mientras quede saldo neto.
- **Una factura no aparece reflejada como saldada en el presupuesto.**
  La factura enlaza con el cobro desde el módulo `billing`. Asegúrate
  de que el cobro está asignado al presupuesto correcto.
