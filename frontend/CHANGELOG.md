# Changelog — frontend

## Unreleased
- test(a11y/touch): la auditoría cubre también los **estados fríos** del
  presupuesto público —rechazado, caducado y bloqueado por intentos—, que
  son los que ve un paciente cuando algo ha salido mal y por eso los que
  nadie mira. Su único control es el «Llamar a la clínica», que es
  justamente lo que la pantalla existe para ofrecer.

  *Caducado* y *bloqueado* son banderas de la llamada `meta`, así que se
  producen respondiendo esa llamada de otra forma. **No se altera ningún
  presupuesto para verlos**: caducar uno real o bloquear un enlace real
  dejaría la ficha de un paciente en un estado que se inventó un test.

- test(a11y/touch): la **página pública del presupuesto** entra en la
  auditoría táctil, en sus tres estados: la verificación, el presupuesto y
  el diálogo de *Aceptar y firmar*. Es la única superficie que toca un
  paciente en su propio dispositivo y donde se acepta y se firma un plan, y
  era justo la que no se auditaba — por eso la casilla de 16 px llevaba
  tiempo ahí.

  Nada va escrito a mano: el seed genera un `public_token` nuevo en cada
  siembra, así que el test descubre presupuesto, token y dígitos de
  verificación por la API con la sesión que ya tiene. Nunca acepta ni
  rechaza: ambas peticiones están bloqueadas además de no pulsarse. Deja una
  única huella, marcar el presupuesto como visto, que es lo que hace el
  producto ante cualquier visita.

- fix(a11y/touch): las casillas de Nuxt UI eran un blanco de **16 px** en
  tablet, y se dibujaban como píldoras altas.

  Nuxt UI no renderiza un `input`: renderiza `button[role="checkbox"]` con
  una caja `size-4` y un `<span>` indicador dentro. Eso las metía en la
  regla genérica de botones —44 px de alto, ancho intacto: una píldora de
  16×44, visible como cápsulas azules en la columna *Visible* del
  catálogo— y a la vez las dejaba fuera de la regla de ancho para botones
  de solo icono, cuya prueba es «ningún `<span>` hijo con contenido»: el
  indicador lleva el tick, así que la casilla se leía como un botón con
  etiqueta.

  Ahora la caja vuelve al tamaño que dibuja y los 44 px salen de un área
  de toque en `::after` que no ocupa maquetación. Hace falta
  `overflow: visible` porque el control trae `overflow: hidden`, que
  recortaría el pseudoelemento; lo que recortaba era el indicador, del
  mismo tamaño que su caja, así que solo cambian las esquinas de 2 px y
  solo en táctil.

  Salió probando el *aceptar y firmar* del presupuesto público: la casilla
  de consentimiento —el control que habilita la firma— medía 16 px de
  ancho. Ahí el efecto era menor porque su etiqueta larga también alterna
  la casilla; donde de verdad dolía es en las casillas **sin etiqueta**,
  como las del catálogo.

- fix(tests): la auditoría táctil medía la caja del control, no el área
  que toca un dedo, así que habría marcado cada casilla como 16×16 en
  cuanto una apareciera en una ruta auditada. Ahora suma el `::after`
  cuando es un área de toque absoluta hacia fuera. Comprobado: 16×16 de
  caja, 44×44 de objetivo.

- fix(a11y): `SettingsLayout` abría un segundo `<main>` dentro del que ya
  abre el layout por defecto. Era el tercero de tres sitios con el mismo
  defecto —los otros dos, en `patients` y en `budget`— y el mismo arreglo:
  pasa a `<div>`. El rail de categorías sigue siendo un `<aside>`, así que
  la estructura de landmarks queda en un `main` por documento.

- fix(e2e): el **flake de arranque en frío del periodontograma**. Verde en
  un servidor caliente, rojo en la primera ejecución tras un reinicio —que
  es justo lo que hace CI—. La sonda que decidía si el parámetro de la URL
  había cambiado de pestaña preguntaba `isVisible()` en el instante en que
  la URL se asentaba, pero `domcontentloaded` salta mientras el servidor de
  desarrollo todavía compila los chunks de la vista clínica: leía «aún no
  hidratado» como «el parámetro no funcionó» y se lanzaba a pulsar botones
  de una página que no estaba lista, hasta agotar el tiempo esperando una
  pestaña que iba a aparecer igualmente.

  Ahora espera antes de decidir, y solo recurre a pulsar si de verdad no
  llega. El fichero además no subía el tope de 30 s por test —el resto de
  specs que abren rutas en frío reservan 120 s— y la ruta tarda ~78 s en
  compilarse la primera vez, así que agotaba el tiempo por sí solo.
- fix(auth): **un render de servidor gastaba un token de refresco y
  presentaba otros tres.** La rotación con detección de reutilización
  (ADR 0029) revoca la familia entera en cuanto ve un token ya gastado, y
  sin ventana de gracia — que es la regla correcta. Lo que estaba mal era
  que la aplicación lo presentaba varias veces ella sola.

  El dedupe del refresco era **solo de cliente**, a propósito: «en el
  servidor los refrescos son por petición y no necesitan dedupe». No es
  cierto. Un render dispara en paralelo el middleware de auth,
  `useClinic`, `useModules` y los fetch de la página; todos se encontraban
  el mismo access token caducado y cada uno llamaba a `refresh()`:

      1 x POST /auth/refresh -> 200   (rota el token)
      3 x POST /auth/refresh -> 401   reutilización -> familia revocada
      3 x POST /auth/logout  -> 204   cada fallo cerraba la sesión otra vez

  Y la respuesta devolvía `refresh_token=; Max-Age=0`: el render había
  gastado el token bueno y le entregaba al navegador un borrado en su
  lugar. Lo que se veía era un parpadeo de la pantalla de login y una
  sesión que seguía funcionando hasta quince minutos más — revocar una
  familia deja `token_version` intacto a propósito, así que el access
  token la sobrevive. Cuál de las cuatro escrituras de cookie quedaba la
  última no era determinista, y de ahí que unas veces echase a login y
  otras no.

  Tres arreglos, y el segundo es el que no era evidente:

  - **El dedupe existe también en SSR**, sobre el contexto de la petición
    —compartido por todo el render y nunca serializado—. Un `useState` no
    vale: una promesa ahí rompe el payload.
  - **Se recuerda el token ya canjeado.** La promesa compartida solo cubre
    a quien llega a la vez; `useCookie` le da a cada instancia su *propia*
    ref, así que una instancia creada antes del canje seguía con el token
    gastado y lo volvía a presentar. Ahora lo reconoce, adopta el par
    recién emitido y responde con el resultado en vez de repetir el canje.
  - **Un refresco fallido ya no llama a `logout()` dos veces.** `refresh()`
    es el único dueño del cierre de sesión; `useApi` y `fetchUser` ya no
    revocan por su cuenta una familia que ya estaba revocada.

  Además, un 401 del `/auth/me` posterior al refresco ya no cierra la
  sesión: a esas alturas el canje ya salió bien.

  Un render con el access token caducado pasa de `1x200 + 3x401` a
  **un solo refresco 200**, sin logout, y con los reintentos en 200.
- test(e2e): la pestaña **Caja** entra en la auditoría táctil, con dos
  pruebas: los controles del formulario de movimiento y —la que importa— que
  el arqueo **no enseña el esperado hasta que se escribe el conteo**. Esa es
  la decisión de producto sobre la que se sostiene toda la función y hasta
  ahora no la sujetaba nada.

  Las dos afirman **sólo estructura**, a propósito: `seed-demo.sh` no crea
  movimientos ni arqueos —no puede, un conteo lo hace una persona— así que
  una prueba que esperase una cifra pasaría en la base de un desarrollador y
  fallaría en CI.

  Y las dos trabajan sobre un **día muy anterior a cualquier cosa que siembre
  la semilla** en lugar de sobre hoy. La base de un desarrollador tiene
  arqueos de verdad, y un día ya contado esconde el botón que la prueba
  necesita: fallaría en local y pasaría en CI, que es la forma menos útil que
  puede tomar un fallo.

  De paso, la segunda esperaba a que el modal terminase de animar antes de
  medir. `getBoundingClientRect` a mitad del `scale` de entrada devuelve 43 px
  para un control de 44, y once controles salían como infradimensionados sin
  que hubiera nada mal en ellos. El mismo `waitForTimeout` está en la prueba
  del diálogo de aceptación, por lo mismo.

  **Sin cobertura e2e de Liquidaciones**, y no es un descuido: el módulo es
  `auto_install=False`, así que no está montado donde corre Playwright y la
  pestaña no existiría. Queda razonado en el CLAUDE.md del módulo.
- feat(types): `PlanDraftLine` gana `requiresSurfaces`. La línea en memoria
  tiene que saber si su tratamiento se describe por caras para poder
  ofrecerlas al editarlo, sin volver a preguntar al catálogo en cada
  render. Motivos y detalle en el CHANGELOG de `treatment_plan`.
- fix(tests): `tablet-touch.spec.ts` parpadeaba en horizontal. La espera de
  hidratación (`awaitDetection`) tenía permitidos 60 s de selector dentro de
  un suite cuyo presupuesto por test es de 30 s, así que una ruta lenta
  mataba el test antes de que su aserción llegara a ejecutarse.

  El reparto no era casual: los cinco tests que fallaban de forma
  intermitente eran exactamente los cinco que seguían con el presupuesto por
  defecto de 30 s; los cinco que ya llevaban `test.setTimeout(180_000)` no
  parpadearon nunca. Medido, «every control outside a dense surface meets the
  44 px minimum» tardaba 25,8 s y 24,0 s contra ese límite de 30 s — un
  margen de cuatro segundos, es decir, una compilación de ruta lenta de
  distancia de morir.

  El arreglo va dentro de `awaitDetection`, que ahora compra el plazo que se
  le permite gastar (`test.setTimeout(test.info().timeout + HYDRATION_TIMEOUT)`).
  Pagarlo ahí y no test a test es lo que evita que el siguiente test que
  alguien añada herede la misma trampa.

- feat(planes): el alta de plan es ahora un odontograma en blanco donde se
  dibuja el tratamiento, y el paciente se pregunta al final. Motivos y
  detalle en el CHANGELOG de `treatment_plan`.

  Lo que toca a este paquete: `PlanDraftLine` se añade a `app/types` (el
  plan mientras vive solo en memoria del navegador), y `TreatmentCatalogItem`
  gana `is_diagnostic` en los resultados de `/catalog/items/search`, que es
  lo que permite dejar los diagnósticos (caries, fractura) fuera de un
  selector de planificación.

- refactor(home): `HomeGreeting` formatea la fecha con `formatInstant`
  (`~/utils/date`) en lugar de repartir a mano la opción `timeZone`. Es el
  mismo ajuste que ya aplican el ledger y «Pendiente de cobrar», y con el
  helper la regla la impone la función, no la memoria de quien escribe la
  siguiente pantalla.

  Sobrevive un `zone` local, para el saludo: ese cálculo saca la **hora como
  número** con `Intl.DateTimeFormat(...).format()` en vez de renderizar una
  fecha, así que no cabe en el helper. Queda anotado en el sitio.

  Sin cambio de comportamiento: `formatInstant` hace exactamente lo que hacía
  el código anterior, así que la precaución de hidratación que documenta la
  cabecera de ese fichero —servidor y cliente formateando el mismo instante
  en la misma zona— sigue en pie.

- fix(a11y): la interfaz hablaba en inglés a los lectores de pantalla. Eran
  **dos** problemas distintos, con arreglos distintos:
  - **Mensajes de Nuxt UI** (el botón de tema anunciaba «Switch to dark
    mode»). `UApp` no recibía idioma, así que usaba el inglés interno; ahora
    se le pasa el locale español de Nuxt UI, atado al idioma de la app para
    que un cambio mueva los dos a la vez.
  - **Etiquetas fijas de Reka UI**: el disparador de `USelectMenu` lleva
    `aria-label="Show popup"` escrito a fuego y **nunca** consulta el locale,
    ni el de Nuxt UI ni el suyo. Como ese botón *es* el control del select y
    está en el orden de tabulación (`tabindex="0"`), los 27 selects de la app
    se anunciaban como «Show popup» en vez de por su propósito. Se sobrescribe
    con un `aria-label` explícito por control: el del campo cuando hay
    `UFormField`, el `placeholder` cuando no, y uno elegido en los tres que no
    tenían ninguno. Mejor que una traducción genérica: cada select dice qué es.
- fix(i18n): la × de `SearchBar` y las flechas de año de `MonthPickerDropdown`
  tenían el `aria-label` en inglés a pelo. Traducidas
  (`common.clearSearch`, `recalls.filters.previousYear` / `nextYear`).
  No queda ningún `aria-label` sin traducir en el frontend ni en los módulos.
- fix(listas): en tablet vertical con el raíl desplegado, el botón **Filtros**
  se dibujaba encima del control de orden, que quedaba recortado a un trozo
  ilegible. Afectaba a Pacientes, Cobros, Presupuestos y Facturas —las cuatro
  listas con orden—; Profesionales se libraba por no tenerlo. `FilterBar`
  colapsa los chips a un botón precisamente para no tapar el orden, y hacía
  lo contrario: la zona de chips es `flex-1 min-w-0` y se encogía a ~8 px
  mientras el botón, posicionado en absoluto, seguía midiendo 78 px y se
  salía. Ahora el botón va en el flujo y la zona usa `min-w-fit` mientras lo
  muestra, y la búsqueda deja de ser `shrink-0` para que los tres controles
  quepan. En horizontal la barra no cambia.
  El aprieto real es *lienzo estrecho con viewport ancho*: por debajo de `md`
  la zona de chips ni se renderiza, así que estrechar la ventana no reproduce
  nada — hay que desplegar el raíl, que es lo que hace el test.
- fix(auth): los formularios públicos con SSR — login y el asistente de
  instalación — declaran `method="post"`, y su botón de envío queda
  deshabilitado hasta que la página hidrata. Se renderizan en el servidor, así
  que entre que se pinta el HTML y carga el bundle de Vue el `@submit.prevent`
  todavía no está puesto: un Enter en ese hueco disparaba el envío nativo del
  navegador, y un `<form>` sin `method` es un GET a la URL actual. Los campos
  se llaman `email` y `password`, de modo que la contraseña acababa en la barra
  de direcciones, en el historial y en el log de accesos — y el usuario, de
  vuelta en el formulario vacío.

  En `setup.vue` sólo el paso 1 necesita la guarda: al paso 2 no se llega sin
  haber hidratado. `tests/pages/publicSsrForms.test.ts` fija la regla para los
  tres formularios públicos del repo.

- feat(config): `treatmentPhases.ts` — el orden clínico de las fases, en un
  solo sitio. Lo tenía el filtro del catálogo como constante local y ahora
  lo necesita también la lista del plan; dos órdenes distintos habrían
  puesto el mismo plan en dos secuencias según la pantalla.

- fix(odontogram config): `getVisualizationRuleLayers` converts a treatment
  type's rules into the layer objects the catalog persists, in one place. The
  two existing copies had already drifted — one emitted bare rule names, which
  the API rejects.


- fix(lint): ESLint now covers the module layers. Every module ships a Nuxt
  layer under `backend/app/modules/<name>/frontend/`, roughly half of the UI
  code, and the config lived inside `frontend/` — so ESLint's base path was
  that directory and `eslint .` reported success on code it had never opened.
  Pointing it at a layer file failed outright with "File ignored because
  outside of base path".

  The config moves to the repo root. That costs one thing: the Nuxt-generated
  config scopes `vue/multi-word-component-names` and
  `vue/no-multiple-template-root` by directory with globs relative to the
  config file, and those stop matching once the root moves. Both are restated
  for the host app *and* the layers — which Nuxt could not cover anyway, so
  pages inside a module never had them.

  Uncovering the layers surfaced 1859 findings. 1212 were auto-fixed
  formatting; ~30 more were dead `useI18n()` destructuring, unused imports and
  compact one-liners. The 18 that need a judgement call in modules this change
  did not touch — dead declarations, four `any`s in verifactu, three pages with
  multiple template roots, a `v-memo` inside a `v-for` that does nothing, one
  dynamic `delete` — warn instead of erroring, listed on every run. See the
  `dentalpin/layers/pre-existing` block in `eslint.config.mjs`.
