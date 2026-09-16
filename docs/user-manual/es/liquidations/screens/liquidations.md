---
module: liquidations
screen: liquidations
route: /finanzas?tab=liquidations
related_endpoints:
  - GET /api/v1/liquidations
  - GET /api/v1/liquidations/preview
  - GET /api/v1/liquidations/commissions
  - GET /api/v1/liquidations/{liquidation_id}
  - POST /api/v1/liquidations
  - POST /api/v1/liquidations/{liquidation_id}/pay
  - POST /api/v1/liquidations/{liquidation_id}/unpay
  - PUT /api/v1/liquidations/commissions/{professional_id}
related_permissions:
  - liquidations.settlement.read
  - liquidations.settlement.issue
  - liquidations.commission.write
related_paths:
  - backend/app/modules/liquidations/frontend/components/finance/LiquidationsTab.vue
  - backend/app/modules/liquidations/router.py
  - backend/app/modules/liquidations/service.py
last_verified_commit: 934bc23
---

# Liquidaciones

> **Dónde está.** Pestaña **Liquidaciones** de **Finanzas**, la última.
> Solo aparece si el módulo está instalado.

Aquí se liquida a un odontólogo asociado por un periodo. El periodo viene
puesto en la **quincena de calendario** —del 1 al 15 o del 16 a fin de mes—
porque es cuando se paga la nómina, y se puede cambiar.

## Los dos números

- **Devengado**: el trabajo que hizo en el periodo, valorado. Cobrado o no.
- **Cobrado**: lo que el paciente ya ha pagado **de ese trabajo**.

El recuadro azul marca sobre cuál de los dos se aplica el porcentaje. Abajo,
línea a línea, cada tratamiento con lo que devengó y lo que se ha cobrado de
él; **en ámbar lo que todavía no está cobrado del todo**.

> **Cómo se sabe qué pagos corresponden a qué trabajo.** Un pago no apunta a
> un tratamiento concreto: el dinero del paciente cubre sus cargos más
> antiguos primero. Así que si un paciente debía trabajo anterior, lo que
> paga hoy va a ese trabajo antes que al del periodo que estás liquidando —
> aunque lo haya hecho otro profesional.

## El acuerdo

> Requiere `liquidations.commission.write`.

**Cambiar el acuerdo** abre el porcentaje y la base: *sobre lo cobrado* o
*sobre lo devengado*. Se puede cambiar cuando haga falta; **las
liquidaciones ya emitidas guardan el porcentaje con el que se hicieron**, así
que renegociar en marzo no toca lo de enero.

Mientras no haya acuerdo registrado, la pantalla lo dice en ámbar y no deja
emitir. Las cifras de trabajo son reales igualmente: lo que falta es el
reparto, no los datos.

## Emitir

> Requiere `liquidations.settlement.issue`.

**Emitir la liquidación** congela las cifras. A partir de ahí, lo que el
paciente pague después no cambia lo ya liquidado — que es el punto: es el
número sobre el que alguien cobró.

Un periodo solo se liquida una vez por profesional. Si ya está hecho, la
cabecera lo dice y el botón desaparece.

## Pagar la liquidación

> Requiere `liquidations.settlement.issue`, el mismo permiso que emitirla.

Emitir dice lo que se debe; **Pagar** lo entrega. Son dos actos porque pasan
en momentos distintos: la quincena se cierra el día 15 y al asociado se le
paga cuando viene.

**Si pagas en efectivo, el movimiento de caja se escribe solo.** No hay que
ir a la pestaña Caja a teclear la cifra: aparece ahí como *Pago a
profesional*, con el nombre y el periodo en el concepto, y el arqueo del día
ya lo cuenta. Que alguien copie 699 a mano es exactamente como se descuadra
una caja.

**Por transferencia no toca el cajón.** El dinero llega al banco del asociado
sin que la caja se abra, y anotarle un movimiento dejaría el arqueo corto por
el importe entero.

Una liquidación pagada se marca en verde con cómo se pagó, y al lado queda la
flecha de **deshacer**.

## Deshacer un pago

Si registraste el pago por error, la flecha lo deshace y **se lleva el
movimiento de caja con él**.

Deja de poder hacerse en cuanto el día ya está arqueado: ese movimiento está
dentro de un número que alguien contó y firmó. El camino entonces es reabrir
el día desde la pestaña Caja, deshacer, y volver a contar.

> El movimiento de un pago **no se puede editar ni borrar desde Caja**. Si lo
> intentas te dirá que lo deshagas desde la liquidación — es la única forma de
> que las dos cosas no se contradigan.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver la pestaña y las liquidaciones | `liquidations.settlement.read` |
| Emitir una liquidación, pagarla y deshacer el pago | `liquidations.settlement.issue` |
| Cambiar el porcentaje acordado | `liquidations.commission.write` |

Un odontólogo puede ver lo que se le debe. **Lo que la clínica paga a sus
asociados, y emitir la cifra, son de administración.**

## Resolución de problemas

- **No veo la pestaña.** El módulo es opcional: instálalo desde Ajustes →
  Módulos. Si está instalado, tu rol no tiene `settlement.read`.
- **Sale todo a cero.** Comprueba el periodo y que el trabajo esté marcado
  como realizado: la liquidación lee el devengo, que solo existe cuando un
  tratamiento se ejecuta.
- **El cobrado es mucho menor que el devengado.** Es información, no un
  error: ese trabajo todavía no se ha pagado. Las líneas en ámbar dicen
  cuáles.
- **No me deja emitir.** Falta registrar el acuerdo con ese profesional, o
  el periodo ya está liquidado.
