// @ts-check
//
// One ESLint config for the whole repo, at the root on purpose.
//
// The frontend directory is not the only place Vue and TypeScript live: every
// module ships its own Nuxt layer under `backend/app/modules/<name>/frontend/`,
// and that is roughly half of the UI code. While this config sat inside
// `frontend/`, ESLint's base path was that directory and every layer file was
// silently skipped — `eslint .` reported success on code it had never opened,
// and pointing it at a layer file failed outright with "File ignored because
// outside of base path".
//
// Moving the base path up costs one thing: the Nuxt-generated config scopes a
// couple of rules by directory (`app/pages`, `app/components`…) using globs
// relative to the config file, and those stop matching once the root moves.
// They are restated below for both the host app and the layers — Nuxt cannot
// know about the layers anyway, so pages inside a module never had them.
import withNuxt from './frontend/.nuxt/eslint.config.mjs'

/** Host app and module layers share a structure; only the prefix differs. */
const UI_ROOTS = ['frontend/app', 'backend/app/modules/*/frontend']

const glob = (suffix) => UI_ROOTS.map(root => `${root}/${suffix}`)

export default withNuxt(
  {
    ignores: [
      '**/node_modules/**',
      '**/.nuxt/**',
      '**/.nuxt-test/**',
      '**/.output/**',
      '**/dist/**',
      '**/coverage/**',
      'backend/alembic/**',
      'docs/**'
    ]
  },
  {
    // Mirrors `nuxt/disables/routes`: a route file is named after its URL
    // segment, and a component nested in a folder is already namespaced.
    name: 'dentalpin/disables/routes',
    files: [
      // `app.vue` / `error.vue` have a fixed meaning in Nuxt.
      ...glob('app.{js,ts,jsx,tsx,vue}'),
      ...glob('error.{js,ts,jsx,tsx,vue}'),
      // Layouts and pages are named after the route, never used as tags.
      ...glob('layouts/**'),
      ...glob('pages/**'),
      // A component nested in a folder is already namespaced by it.
      ...glob('components/*/**')
    ],
    rules: {
      'vue/multi-word-component-names': 'off'
    }
  },
  {
    // Mirrors `nuxt/vue/single-root`: layouts and pages render one root.
    name: 'dentalpin/vue/single-root',
    files: [...glob('layouts/**'), ...glob('pages/**')],
    rules: {
      'vue/no-multiple-template-root': 'error'
    }
  },
  {
    // Debt uncovered the day the layers started being linted, not an
    // exemption. Eighteen findings survived the mechanical pass because each
    // needs a judgement call in a module nobody was working on: dead
    // declarations that may be someone's work in progress, four `any`s in
    // verifactu, three pages with multiple template roots, a `v-memo` inside
    // a `v-for` that silently does nothing, and one dynamic `delete`.
    //
    // They warn so the list is printed on every run and CI stays honest
    // instead of red on code this change did not write. Fix them and delete
    // the corresponding line; when the list is empty, delete the block.
    name: 'dentalpin/layers/pre-existing',
    files: ['backend/app/modules/*/frontend/**'],
    rules: {
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-dynamic-delete': 'warn',
      'vue/no-multiple-template-root': 'warn',
      'vue/valid-v-memo': 'warn'
    }
  }
)
