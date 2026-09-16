# Changelog — liquidations module

## Unreleased

- feat(liquidations): **se cierra el círculo del pago**. Hasta ahora la
  quincena terminaba a medias: emitías la liquidación, que decía 699, y
  después ibas a Caja y tecleabas a mano un movimiento de 699. Dos asientos
  sin relación, con la cifra copiada por una persona — y cuando alguien
  teclea 700, o paga en dos veces, o se le olvida, el arqueo cuadra mal y
  nadie sabe por qué.

  `POST /{id}/pay` registra el pago y, **si es en efectivo, escribe el
  movimiento de caja en la misma transacción**.

  **Llamada directa, no evento, y cambié de opinión sobre esto.** El ADR
  0003 hace del bus el camino por defecto para las *reacciones* entre
  módulos, pero esto no es una reacción: el pago y el movimiento son un
  mismo hecho visto dos veces. Un handler que corre después del commit puede
  fallar —el bus lo anota y no reintenta— y lo que queda es una liquidación
  que dice «pagada» sin que haya salido dinero del cajón: exactamente la
  divergencia silenciosa contra la que existe todo el trabajo de caja. El
  precedente es `treatment_plan.confirm()` llamando a
  `BudgetService.create_from_plan_snapshot` de forma síncrona, documentado
  allí como *el carve-out*.

  - **Solo el efectivo toca el cajón.** Una transferencia llega al banco del
    asociado sin que la caja se abra, e inventarle un movimiento dejaría el
    siguiente arqueo corto por el importe entero — un fallo que se parece a
    un robo.
  - **Categoría propia en `cashbox`: `professional_payout`.** Un adelanto se
    descuenta después y una liquidación ya es el pago; un informe que no las
    separa no sirve para ninguna de las dos.
  - **El movimiento no se edita desde Caja.** `cashbox` rechaza editar o
    borrar una fila de esa categoría leyendo la categoría, sin preguntarle
    nada a este módulo. Borrar ya era imposible por la FK pero llegaba como
    un 500; editar era peor, porque funcionaba y dejaba a la liquidación
    afirmando un importe que la caja nunca movió.
  - **Deshacer existe**, porque un pago equivocado irreversible es lo que
    hace que la gente deje de fiarse de una pantalla — y se detiene donde se
    detiene todo lo demás: una vez arqueado el día, el movimiento está dentro
    de un número que alguien firmó y hay que reabrirlo.
  - **Un pago en un día ya contado es un apunte posterior**, que la fase 4
    de `cashbox` ya resuelve sin una línea de código aquí.

  El estado de pago vive en la fila de `liquidations`: se paga una vez, y
  «emitida pero no pagada» es un estado del documento, no un evento con vida
  propia. No contradice el congelado — las cifras liquidadas no se mueven; lo
  que se añade es un hecho posterior sobre ellas.

- feat(liquidations): nace el módulo. Liquidar a un odontólogo asociado a
  porcentaje, que es lo que más valor tenía de todo lo que quedaba pendiente
  del trabajo de caja.

  **Todo gira sobre dos números que no son el mismo número**: lo que el
  asociado **devengó** —el trabajo que hizo, valorado— y lo que se ha
  **cobrado** de ese trabajo. En un caso de 19.000 MXN los dos van con meses
  de diferencia, y pagar un porcentaje del primero es repartir dinero que la
  clínica todavía no ha recibido. La mayoría de las clínicas mexicanas paga
  sobre lo cobrado, así que ése es el valor por defecto — pero **se calculan
  y se enseñan los dos**, porque ninguno se puede juzgar sin el otro, y cuál
  de los dos se paga es un acuerdo que la clínica registra por persona.

  **Cómo se atribuye el dinero a un profesional.** No hay clave ajena entre
  un pago y el trabajo que paga: `payments` los casa FIFO —el dinero del
  paciente cubre sus cargos más antiguos primero— y el nuevo
  `LedgerService.coverage_by_earned_entry` proyecta ese recorrido sobre los
  devengos. Como cada devengo lleva el profesional que hizo el trabajo,
  cubrir los devengos **es** atribuir el dinero.

  El recorrido pasa por **todos** los devengos del paciente y no solo los de
  este profesional: quien pagó 6.000 contra las obturaciones del mes pasado
  no tiene nada disponible para el cirujano de este mes, y un recorrido
  restringido a un profesional acreditaría el mismo dinero dos veces. Por
  eso el lector vive en `payments` y no aquí.

  - **Emitir congela.** `lines`, `percent` y `basis` se copian al documento.
    Que un paciente pague mañana por trabajo de la quincena pasada no puede
    cambiar lo que alguien ya cobró; que el porcentaje se renegocie en marzo,
    tampoco.
  - **El acuerdo es mutable justamente por eso.** Mismo principio que el
    arqueo: el documento es el registro, el ajuste solo es de dónde parte el
    siguiente.
  - **Sin acuerdo registrado se dice, no se supone.** La vista previa
    devuelve el trabajo con `missing_commission` y un cero, y emitir se
    rechaza: dar a alguien un cero con seguridad es peor que decirle que el
    porcentaje no está acordado.
  - **Sin identidad del paciente.** La liquidación va a un asociado y nombra
    el trabajo, no a las personas; el módulo no depende de `patients`.
  - Las sesiones de un tratamiento se pliegan en una línea: el asociado lee
    un trabajo, no una fila por visita.

  La migración usa `depends_on = ("professionals",)` en lugar de colgar
  `down_revision` de la cabeza de esa rama: las dos tablas apuntan a
  `professionals.id` y tienen que ir después, pero enhebrar una rama en otra
  es lo que arrastraría este módulo a un `alembic downgrade
  professionals@base` (issue #56, ADR 0002).

  Un porcentaje por profesional en esta versión. Las clínicas que reparten
  por disciplina —40 % en ortodoncia, 50 % en cirugía— existen; el punto de
  extensión es una tabla hija por categoría de catálogo y nada de esto
  cambia.
