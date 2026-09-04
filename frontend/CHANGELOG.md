# Changelog — frontend

## Unreleased
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
