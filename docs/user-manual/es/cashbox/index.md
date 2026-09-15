---
module: cashbox
last_verified_commit: f2ce026
---

# Caja (cashbox)

El módulo de caja lleva **el cajón**: el dinero en efectivo que entra y
sale de la clínica sin ser un cobro de un paciente.

No se solapa con Cobros. Cobros responde «cuánto nos pagaron»; Caja
responde «qué hay ahora mismo en el cajón y por qué». Un pago en efectivo
de un paciente suma a las dos cosas, pero el mensajero del laboratorio al
que le pagas 450 pesos no aparece en Cobros y vacía el cajón igual.

## Qué hay hoy

El módulo está completo: los movimientos, el arqueo diario, los cortes por
semana, quincena y mes, y los apuntes que llegan con fecha de un día ya
contado.

Lo que **no** cubre, a propósito: la liquidación a los odontólogos
asociados y la comisión de la terminal. Las dos merecen existir y las dos
arrastran decisiones propias.

## Pantallas

- [Caja](./screens/cashbox.md) — pestaña de Finanzas.
