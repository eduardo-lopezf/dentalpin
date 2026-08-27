/**
 * Typecheck the host **and every module layer**, and fail on anything the
 * baseline does not already know about.
 *
 * Why a baseline: CI used to stub an empty `modules.json` and then only
 * run `nuxi prepare`, so no layer was ever typechecked and no typecheck
 * ever ran. Hundreds of errors accumulated behind a green build. Turning
 * the gate on all at once would mean either a red CI or a mass rewrite;
 * the baseline freezes what is already broken, fails the build on
 * anything new, and shrinks as the backlog is worked off.
 *
 *   node scripts/typecheck-gate.mjs            # gate (CI)
 *   node scripts/typecheck-gate.mjs --update   # re-freeze the baseline
 *
 * Errors are keyed by file + code + message with line/column dropped, so
 * editing a file above an error does not churn the baseline. The count per
 * key is part of the baseline, so a *new occurrence* of an already-known
 * error still fails.
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const baselinePath = resolve(frontendRoot, 'typecheck-baseline.json')
const manifest = 'modules.ci.json'
// Never `.nuxt`: a dev server in a container runs against this same
// mounted directory, and concurrent writes corrupt its build.
const buildDir = process.env.NUXT_BUILD_DIR ?? '.nuxt-typecheck'
const update = process.argv.includes('--update')

const ERROR_RE = /^(?<file>[^(]+)\((?<line>\d+),(?<col>\d+)\): error (?<code>TS\d+): (?<message>.*)$/

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: frontendRoot,
    encoding: 'utf-8',
    env: {
      ...process.env,
      DENTALPIN_MODULES_JSON: manifest,
      NUXT_BUILD_DIR: buildDir
    },
    maxBuffer: 64 * 1024 * 1024
  })
  return `${result.stdout ?? ''}${result.stderr ?? ''}`
}

run('node', ['scripts/write-module-layers.mjs', manifest])
run('npx', ['nuxt', 'prepare'])
// `nuxt typecheck` resolves `.nuxt/tsconfig.json` regardless of
// `buildDir`, which meant it silently checked the dev server's config —
// whose layer paths only exist inside the container, so nothing but the
// host app got checked (11 errors instead of 194). Point `vue-tsc` at
// the config we just generated instead.
const output = run('npx', ['vue-tsc', '-b', `${buildDir}/tsconfig.json`])

const errors = []
for (const line of output.split('\n')) {
  const match = ERROR_RE.exec(line.trim())
  if (!match) continue
  const { file, code, message } = match.groups
  // Paths differ between a checkout and CI only by prefix; keep the part
  // that identifies the source file.
  const normalizedFile = file.replace(/^.*?(app|backend)\//, '$1/')
  errors.push({ key: `${normalizedFile}|${code}|${message}`, line: line.trim() })
}

const counts = new Map()
for (const error of errors) counts.set(error.key, (counts.get(error.key) ?? 0) + 1)

if (update) {
  const frozen = Object.fromEntries([...counts.entries()].sort(([a], [b]) => a.localeCompare(b)))
  writeFileSync(
    baselinePath,
    `${JSON.stringify({ total: errors.length, errors: frozen }, null, 2)}\n`
  )
  console.log(
    `[typecheck-gate] baseline re-frozen: ${errors.length} error(s) across ${counts.size} kind(s)`
  )
  process.exit(0)
}

if (!existsSync(baselinePath)) {
  console.error('[typecheck-gate] no baseline; run with --update first')
  process.exit(1)
}

const baseline = new Map(Object.entries(JSON.parse(readFileSync(baselinePath, 'utf-8')).errors))
const introduced = []
for (const [key, count] of counts) {
  const allowed = baseline.get(key) ?? 0
  if (count > allowed) {
    const examples = errors.filter(e => e.key === key).slice(allowed)
    introduced.push(...examples.map(e => e.line))
  }
}

const fixedCount = [...baseline.entries()]
  .map(([key, allowed]) => allowed - (counts.get(key) ?? 0))
  .filter(delta => delta > 0)
  .reduce((a, b) => a + b, 0)
if (fixedCount) {
  console.log(
    `[typecheck-gate] ${fixedCount} baseline error(s) no longer occur — `
    + 'run `node scripts/typecheck-gate.mjs --update` to lock the improvement in.'
  )
}

if (introduced.length) {
  console.error(`\n[typecheck-gate] ${introduced.length} new type error(s):\n`)
  for (const line of introduced) console.error(`  ${line}`)
  console.error('\nFix them, or if the change is deliberate, re-freeze the baseline.')
  process.exit(1)
}

console.log(`[typecheck-gate] no new type errors (${errors.length} known, all baselined)`)
