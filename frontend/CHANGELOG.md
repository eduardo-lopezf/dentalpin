# Changelog — frontend

## Unreleased
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
