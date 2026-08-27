/**
 * Write a `modules.json` whose layer paths resolve in *this checkout*.
 *
 * At runtime the backend writes that file with container paths
 * (`/module_layers/<name>/frontend`), which only resolve inside the
 * frontend container. CI has neither the container nor a database, so it
 * used to stub an empty file — and that is why no module layer had ever
 * been typechecked: type errors accumulated behind a green build.
 *
 * This emits repo-relative paths instead, so `nuxt typecheck` sees
 * exactly the layers that ship in the image.
 *
 *   node scripts/write-module-layers.mjs [outfile]
 *
 * Default outfile is `modules.ci.json`, which `nuxt.config.ts` reads when
 * `DENTALPIN_MODULES_JSON` points at it — so a developer's real
 * `modules.json` (written by their running backend) is never clobbered.
 */
import { existsSync, lstatSync, readdirSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const modulesRoot = resolve(frontendRoot, '..', 'backend', 'app', 'modules')
const outfile = resolve(frontendRoot, process.argv[2] ?? 'modules.ci.json')

if (!existsSync(modulesRoot)) {
  console.error(`[write-module-layers] no modules directory at ${modulesRoot}`)
  process.exit(1)
}

const modules = readdirSync(modulesRoot, { withFileTypes: true })
  .filter(entry => entry.isDirectory() && !entry.name.startsWith('_') && !entry.name.startsWith('.'))
  // A Nuxt layer is a directory with its own nuxt.config — a module may
  // ship a `frontend/` folder of loose assets without being one.
  .filter(entry => existsSync(join(modulesRoot, entry.name, 'frontend', 'nuxt.config.ts')))
  .map(entry => ({ name: entry.name, path: `../backend/app/modules/${entry.name}/frontend` }))
  .sort((a, b) => a.name.localeCompare(b.name))

// Node resolves bare imports by walking *up* from the importing file, and
// a layer at `backend/app/modules/<name>/frontend` never reaches
// `frontend/node_modules` — so every `import { marked } from 'marked'` in
// a layer reads as "cannot find module" to `vue-tsc` even though Vite
// resolves it. One link at the modules root puts the host's packages on
// that walk. Build artifact: gitignored, and nothing reads it at runtime.
const nodeModulesLink = join(modulesRoot, 'node_modules')
try {
  if (lstatSync(nodeModulesLink, { throwIfNoEntry: false })) unlinkSync(nodeModulesLink)
  symlinkSync(join(frontendRoot, 'node_modules'), nodeModulesLink, 'dir')
} catch (err) {
  console.warn(`[write-module-layers] could not link node_modules: ${err.message}`)
}

writeFileSync(
  outfile,
  `${JSON.stringify({ version: 1, layers: modules.map(m => m.path), modules }, null, 2)}\n`
)

console.log(`[write-module-layers] ${modules.length} layers -> ${outfile}`)
