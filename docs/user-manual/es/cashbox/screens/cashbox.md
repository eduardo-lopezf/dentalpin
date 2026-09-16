---
module: cashbox
screen: cashbox
route: /finanzas?tab=cashbox
related_endpoints:
  - GET /api/v1/cashbox/movements
  - GET /api/v1/cashbox/position
  - GET /api/v1/cashbox/periods
  - GET /api/v1/cashbox/late-entries
  - POST /api/v1/cashbox/late-entries/acknowledge
  - GET /api/v1/cashbox/closings
  - GET /api/v1/cashbox/closings/{closing_id}
  - POST /api/v1/cashbox/closings
  - POST /api/v1/cashbox/closings/{closing_id}/reopen
  - GET /api/v1/cashbox/movements/totals
  - GET /api/v1/cashbox/movements/{movement_id}
  - POST /api/v1/cashbox/movements
  - PUT /api/v1/cashbox/movements/{movement_id}
  - DELETE /api/v1/cashbox/movements/{movement_id}
related_permissions:
  - cashbox.movement.read
  - cashbox.movement.write
  - cashbox.closing.read
  - cashbox.closing.write
  - cashbox.closing.reopen
related_paths:
  - backend/app/modules/cashbox/frontend/components/finance/CashboxTab.vue
  - backend/app/modules/cashbox/frontend/components/CashMovementModal.vue
  - backend/app/modules/cashbox/frontend/components/CashClosingCard.vue
  - backend/app/modules/cashbox/frontend/components/CashPeriodCard.vue
  - backend/app/modules/cashbox/frontend/components/CashLateEntriesCard.vue
  - backend/app/modules/cashbox/router.py
last_verified_commit: f2ce026
---

# Caja

> **Dónde está.** Pestaña **Caja** de **Finanzas**, entre Cobros y
> Presupuestos.

Aquí se apunta el efectivo que entra o sale del cajón **sin ser un cobro
de un paciente**: lo que se le paga al mensajero del laboratorio, el
material comprado con dinero del cajón, un adelanto a alguien de la
clínica, lo que se lleva al banco, el cambio que se mete o se saca del
fondo.

## De un vistazo

- **Se trabaja por días.** El selector de arriba elige el día; todo lo
  demás en la pantalla es de ese día. Un cajón se cuenta por días, así que
  no hay rango de fechas.
- **Entradas y salidas van por separado, nunca sumadas.** Un día de 5.000
  que entran y 5.000 que salen no es un día tranquilo, y una sola cifra
  neta contaría las dos cosas como cero. Por eso el neto lleva además el
  número de movimientos.
- **Los cobros de pacientes no se apuntan aquí.** Van en Cobros, y el
  arqueo los leerá de ahí cuando llegue.

## Registrar un movimiento

> Requiere `cashbox.movement.write`.

1. **Registrar movimiento**.
2. **Dirección**: *Sale dinero* (lo normal) o *Entra dinero*.
3. **Importe**, siempre positivo. El signo lo pone la dirección, no el
   número.
4. **Fecha**: el día al que pertenece. Viene puesto el día que estás
   viendo.
5. **Categoría**: Laboratorio, Material, Adelanto, Pago a profesional,
   Depósito a banco, Ajuste de fondo u Otro. *Pago a profesional* la
   escribe sola la pestaña Liquidaciones al pagar a un asociado en
   efectivo, y esas filas no se editan aquí. La lista es corta a propósito para que nadie
   tenga que pensar en el mostrador; el detalle va en el concepto.
6. **Concepto**, obligatorio. Es lo que hará entendible la fila dentro de
   tres meses: «guantes de nitrilo, farmacia de la esquina» dice algo que
   «Material» por sí solo no dice.
7. **Referencia**, opcional: número de ticket o de factura.

## Corregir o quitar

El lápiz corrige la fila y la papelera la quita, **mientras el día siga
abierto**. Se puede cambiar cualquier cosa, incluida la fecha: apuntar un
movimiento en el día equivocado es la corrección más frecuente que hay, y
no debería obligar a borrar y reescribir.

Cuando el arqueo llegue y alguien cierre el día, esas filas pasan a formar
parte de un recuento que una persona contó y firmó: la fila se marca como
**Día cerrado** y pierde los botones. Para tocarla habrá que reabrir el
día, que será cosa de administración.

## El arqueo

> Requiere `cashbox.closing.write`.

La tarjeta **Arqueo de caja**, debajo de los movimientos, es donde se cierra
el día. Antes de contar enseña **las cuentas** —fondo inicial, cobrado en
efectivo, devuelto en efectivo, entradas y salidas— pero **no el total al
que suman**. Es a propósito: si la pantalla dice «deberías tener 4.350» y
luego te pide que cuentes, se teclea 4.350, la diferencia sale cero todos
los días y en un año de arqueos no hay nada que mirar.

1. **Hacer el arqueo**.
2. **Fondo inicial**: lo que había en el cajón al abrir. Viene del último
   arqueo; cámbialo si no era eso.
3. **Contado**: cuenta el cajón y escribe lo que hay. En cuanto escribes un
   número aparecen el **esperado** y la **diferencia**.
4. **Qué pasó**: obligatorio si la cuenta no cuadra. Sobrar es tan
   significativo como faltar.
5. **Se queda para mañana**: el fondo que dejas. El resto sale del cajón, y
   ese fondo será el inicial del próximo arqueo.
6. **Cerrar el día**.

Sólo se cuenta el **efectivo**. Lo que entró por tarjeta o transferencia
aparece aparte, como información: un lote de terminal se concilia contra la
propia terminal y una transferencia llega al banco por su cuenta. Meterlo
todo en el mismo conteo es la forma más rápida de que el arqueo no sirva.

Una devolución hecha en efectivo vacía el cajón aunque el cobro original
fuera con tarjeta, y por eso cuenta; una devolución por transferencia de un
cobro en efectivo, no.

## Reabrir un día

> Requiere `cashbox.closing.reopen`, que por defecto sólo tiene
> administración.

Reabrir deja el conteo sin efecto y devuelve los movimientos del día a
editables. Pide un motivo, y **el conteo anterior no se borra**: queda en el
histórico junto al nuevo. Eso es deliberado — que falten 20 pesos un martes
es ruido, que falten 500 todos los viernes es una señal, y borrar el conteo
viejo eliminaría justo la evidencia.

## El corte del periodo

> Requiere `cashbox.closing.read`.

La tarjeta **Corte del periodo**, al final de la pestaña, resume la
**semana**, la **quincena** o el **mes** que contiene el día que estés
viendo. La quincena es de calendario: del 1 al 15 y del 16 a fin de mes,
que es como se paga la nómina.

Lo importante de esta tarjeta no son los totales, es la línea en ámbar:
**«Faltan N día(s) por contar»**, con los días listados. Son días en los que
se movió dinero del cajón y nadie hizo el arqueo, y **sus importes no están
sumados** en el resto de la tarjeta. Un corte construido sumando pagos se
vería completo aunque nadie hubiera contado nada en toda la quincena; éste
se construye desde los arqueos justamente para poder decirlo.

Un día solo entra en esa lista si hubo movimiento de efectivo: cobrado en
efectivo, devuelto en efectivo o un movimiento de caja. Un día de solo
tarjeta no toca el cajón, y un domingo cerrado no aparece.

**La diferencia del periodo se suma con signo.** Si un día faltaron 50 y al
siguiente sobraron 50, la quincena cuadra de verdad — por eso debajo va
«N día(s) no cuadraron», que es el número que conviene mirar. La lista de
abajo da el detalle día a día con su explicación: una diferencia suelta es
ruido, el patrón es la información.

## Apuntes posteriores al corte

> Requiere `cashbox.closing.read` para verlos y `cashbox.closing.write` para
> anotarlos.

Recepción apunta el efectivo del viernes el lunes, y el viernes ya estaba
contado. **Se permite** — prohibirlo solo conseguiría que lo apuntaran con
fecha de hoy — y el conteo del viernes **no se mueve**: eso es lo que
significa firmarlo. Lo que pasa es que aparece esta tarjeta.

Sale en ámbar, con lo que suman los apuntes y una línea por cada uno: el
día al que pertenecen, qué son (cobro en efectivo, devolución o movimiento)
y su importe, firmado por su efecto sobre el cajón. **Si no hay nada, la
tarjeta no aparece**; una tarjeta que casi siempre está vacía enseña a la
gente a saltarse el sitio donde luego saldrá el aviso.

Cada apunte termina de una de dos maneras:

- **Reabrir el día y volver a contarlo**, desde la tarjeta del arqueo. Al
  contar otra vez con el apunte dentro, deja de estar pendiente.
- **Anotar qué se hace con él.** Pide un texto obligatorio —«visto» no es
  una decisión sobre la que nadie pueda actuar dentro de tres meses— y con
  eso desaparece de la lista. No se borra: queda con quién lo anotó y
  cuándo.

Un cobro con tarjeta nunca aparece aquí: no entró en el cajón, así que el
conteo que se perdió no iba sobre él.

## Permisos

| Lo que ves / puedes hacer | Permiso |
|---------------------------|---------|
| Ver la pestaña y los movimientos | `cashbox.movement.read` |
| Registrar, corregir y quitar movimientos | `cashbox.movement.write` |
| Ver el arqueo, el histórico y el corte del periodo | `cashbox.closing.read` |
| Contar el cajón y cerrar el día | `cashbox.closing.write` |
| Reabrir un día ya cerrado | `cashbox.closing.reopen` |

Recepción cuenta y cierra: es quien abre el cajón. **Reabrir no es suyo**,
porque tira un conteo que alguien firmó. Higienistas no tienen ninguno.

## Resolución de problemas

- **No veo la pestaña Caja.** Tu rol no tiene `cashbox.movement.read`.
- **El importe no me deja poner un número negativo.** Es a propósito: se
  cambia la dirección a *Sale dinero*. Un número negativo en un listado de
  caja se lee como una corrección, no como una salida.
- **No me deja guardar.** Falta el concepto o el importe es cero. El botón
  se enciende cuando los dos están.
- **Un movimiento está en el día equivocado.** Ábrelo con el lápiz y
  cámbiale la fecha; no hace falta borrarlo.
