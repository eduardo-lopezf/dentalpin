# Changelog — cashbox module

## Unreleased

- feat(cashbox): los **apuntes posteriores al corte**. Recepción registra el
  efectivo del viernes el lunes y el viernes ya estaba contado. Prohibir la
  retrodatación solo consigue que lo apunten con fecha de hoy y mientan, así
  que se permite: **el conteo firmado conserva sus cifras** y el apunte sale
  a la luz aquí.

  Lo que hace tarde a un apunte no es la misma prueba en los tres casos, y
  por eso no es una sola consulta: un **cobro** o una **devolución** llegan
  tarde si se *escribieron* después de firmar el día
  (`created_at > closing.closed_at`); un **movimiento** llega tarde si su
  día está cerrado y todavía no tiene `closing_id`, porque cerrar estampa
  todas las filas abiertas del día.

  - **Cada fila termina de una de dos maneras**, y la tarjeta dice las dos:
    o se reabre el día y se vuelve a contar, o alguien anota qué se hace
    con ella. Sin un sitio donde decir «visto, entra en el arqueo de
    mañana» la lista solo crece, y un aviso que está siempre encendido es
    un aviso que nadie lee — el mismo fallo que mata un arqueo cuya
    diferencia nunca es cero. La tarjeta se esconde entera cuando no hay
    nada, por lo mismo.
  - **El texto de la resolución es obligatorio.** «Visto» no es una
    decisión sobre la que nadie pueda actuar dentro de tres meses.
  - **Anotar es `closing.write`, no `closing.reopen`**: decidir que un
    apunte pasa al siguiente conteo es cosa de quien cuenta y no toca nada
    firmado; reabrir el día es la otra respuesta y sigue siendo de
    administración.
  - **Los importes van firmados** por su efecto sobre el cajón, así que
    sumar la lista dice lo que ese día leería si se contase ahora.
  - **Sin identidad del paciente en la respuesta.** El módulo depende de
    `payments` y no de `patients`: un nombre sería a la vez una dependencia
    que el manifiesto no declara y PII en un payload que no la necesita. La
    referencia y el importe bastan para encontrar la fila en Cobros, que es
    donde la persona corresponde.

  `LateEntryAck` apunta a su entrada por `(entry_kind, entry_id)` y no por
  clave ajena, por la misma razón: dos de los tres tipos viven en
  `payments`. `cash_0003` crea la tabla.

- feat(cashbox): los **cortes semanal, quincenal y mensual**, construidos a
  partir de los arqueos diarios y **nunca recalculados desde `payments`**.

  Esa es la decisión de la que depende toda la fase. Recalculada desde los
  pagos, una quincena con tres días que nadie contó se ve impecable;
  montada desde los arqueos puede decir **«faltan 3 días por contar»**, que
  es la frase que un dueño de clínica necesita. Todas las cifras de dinero
  son sumas de `snapshot` congelados, y `pending_days` es lo que reconoce
  el resto.

  - **Un día pendiente es un día en el que se movió dinero y nadie contó**,
    no cualquier día del calendario sin arqueo. Una clínica que cierra los
    domingos tendría si no un aviso de cuatro días de retraso cada mes, el
    aviso estaría mal siempre, y en dos semanas nadie lo leería. Un día
    entra si hubo efectivo cobrado, efectivo devuelto o un movimiento; un
    día de solo tarjeta no toca el cajón y no hay nada que contar.
  - **La quincena es de calendario**: del 1 al 15 y del 16 a fin de mes,
    porque es cuando se paga la nómina. «Cada catorce días» se desfasa del
    mes en marzo y el informe deja de servir para lo único que sirve.
  - **La semana va de lunes a domingo**, igual que agrupa el `trends` de
    `payments`, para que la aplicación tenga una sola semana.
  - **La diferencia del periodo se netea a propósito y `days_off` es lo que
    lo hace seguro.** Una quincena con 50 de menos un día y 50 de más al
    siguiente cuadra de verdad, y decirlo es honesto; lo que no lo sería es
    dejar que se lea como una quincena tranquila.

  `period_bounds` es una función pura y separada del resto justo porque el
  calendario es donde esto se tuerce en silencio: ocho de las veinte
  pruebas de la fase no tocan la base de datos.

- feat(cashbox): el **arqueo diario**. Es el acto por el que existe el
  módulo: alguien cuenta el cajón, declara lo que había, y la diferencia
  entre eso y lo que el sistema esperaba queda congelada. `payments` ya
  sabía decir lo que entró; sólo una persona puede decir lo que hay.

  El esperado sale de cuatro fuentes y la frontera del día es distinta para
  dos de ellas: `Payment.payment_date` ya es un DATE del calendario de la
  clínica y se compara directo, mientras que `Refund.refunded_at` es un
  instante y hay que resolverlo por la zona de la clínica. Una devolución
  entregada a las 20:00 del día 14 en México es el día **15** en UTC, así
  que una ventana hecha con medianoches de UTC la archiva mal y el cajón
  aparece corto cada tarde. Sólo cuenta el **efectivo**: un lote de
  terminal se concilia solo y una transferencia no es dinero de caja.

  **La decisión de producto que hace que esto sirva para algo:** la pantalla
  no enseña el esperado hasta que se escribe el conteo. Enséñale a alguien
  «deberías tener 4.350» y luego pídele que cuente, y teclea 4.350: la
  diferencia sale cero todos los días y un año de arqueos no dice nada. Se
  ven las cuentas —cobrado, devuelto, movimientos— y el total al que suman
  aparece después.

  - **Todas las cifras se guardan, no se derivan.** El esperado es lo que el
    sistema creía en el momento del conteo y sigue siéndolo aunque después
    alguien registre un pago con fecha de ese día. El `snapshot` congela el
    desglose entero por lo mismo: la vista de periodo tiene que leer el día
    como se contó.
  - **Reabrir sustituye, no borra.** La fila pasa a `reopened` y el
    siguiente cierre escribe una nueva, así que el histórico de conteos
    sobrevive. Ese histórico es el producto: que falten 20 un martes es
    ruido; que falten 500 todos los viernes es una señal.
  - **Un solo conteo vigente por día es un índice único parcial**
    (`WHERE status = 'closed'`), no una comprobación del servicio.
  - **La nota es obligatoria cuando la cuenta no cuadra.** Una diferencia
    sin explicar no sirve para nada.
  - **El fondo inicial encadena** con el último conteo *vigente anterior al
    día*, no con el de ayer: las clínicas cierran los domingos y un lunes
    con el fondo a cero declararía perdido el cajón entero.
  - **Reabrir es de administración**, no de quien cuenta: tira un conteo que
    una persona firmó.

  `cash_0002` añade `cash_closings` y la FK que la fase 1 no pudo crear
  porque la tabla destino no existía todavía.

- feat(cashbox): nace el módulo con lo que no existía en ninguna parte: el
  dinero que entra y sale del cajón **sin ser un cobro de paciente**.

  Va primero por una razón concreta. Una caja se vacía todo el día por
  cosas que `payments` nunca va a conocer —se le paga al mensajero del
  laboratorio, se compran guantes, la asistente pide un adelanto, se mete
  cambio de la caja fuerte— y sin un sitio donde anotarlas **el efectivo
  contado no puede cuadrar nunca**. La diferencia sería un número distinto
  de cero todos los días y el arqueo se abandonaría en dos semanas porque
  «siempre marca error». El arqueo llega en la fase 2 y es aritmética
  encima de esto.

  Decisiones que quedan fijadas aquí:

  - **El importe es siempre positivo y la dirección lleva el signo.** Un
    número negativo en un listado de caja se lee como una corrección, y con
    importe con signo la mitad de las filas llevaría uno.
  - **`business_date` es un DATE del calendario de la clínica**, no un
    instante. Con `created_at` un movimiento apuntado a las 00:10 caería en
    el conteo equivocado en cualquier clínica al oeste de Greenwich.
  - **Las entradas y las salidas no se netean.** Un día de 5.000 que entran
    y 5.000 que salen no es un día tranquilo, y una sola cifra neta cuenta
    las dos historias como cero. Por eso el total lleva también el conteo.
  - **El concepto es obligatorio y es texto libre.** «material» es lo que
    un informe puede agrupar; «guantes de nitrilo, farmacia de la esquina»
    es lo que hace que la fila signifique algo en marzo.
  - **Una fila deja de ser editable cuando su día se cierra.** Mientras el
    día está abierto es una nota que alguien dejó y corregirla no cuesta
    nada; después es parte de un registro que una persona contó y firmó, y
    cambiarla en silencio convertiría ese número en una mentira. La regla
    vive en el servicio, no en el router, para que las herramientas del
    agente la hereden.

  `closing_id` ya existe, nullable y siempre nulo: la FK llega con
  `CashClosing` en la fase 2 y nada de esto cambia cuando lo haga.

  Herramientas de agente **solo de lectura**. Registrar un movimiento es
  una afirmación sobre dinero físico —alguien sacó billetes de un cajón y
  dice para qué— y un agente no tiene manera de presenciarlo. Lo que sí
  puede hacer es contestar «¿en qué se fue el efectivo el martes?», que es
  una pregunta que hoy no se podía ni formular.
