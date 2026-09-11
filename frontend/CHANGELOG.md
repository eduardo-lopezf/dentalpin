# Changelog — frontend

## Unreleased
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
