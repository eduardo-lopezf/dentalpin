// npm audit with a reasoned allowlist — ADR 0029.
//
// `npm audit` has no per-advisory exception, so the choice it offers is
// a gate that is red forever or one raised past the severity we care
// about. Both end the same way: nobody reads it. This keeps the gate at
// `high` and lists the exceptions individually, the way
// `tests/test_no_dynamic_sql.py` and the cross-tenant baseline do.
//
// Entries are promises. Each needs a reason that survives review, and
// each should go the moment its fix is reachable.
import { spawnSync } from 'node:child_process'

const ALLOWED = {
  // Fixed in nuxt 4.5.x, which this project cannot take yet: 4.5
  // requires @nuxtjs/i18n v10, and the project is on v9 — bisected, the
  // build fails with two `builtin:vite-json` errors and succeeds with
  // the i18n module removed. That upgrade is a major-version migration
  // and is tracked on its own.
  //
  // Exposure meanwhile is nil rather than merely low: the advisory is
  // that route middleware is skipped when rendering `.server.vue` pages
  // through `/__nuxt_island/page_*`, and this codebase has no
  // `.server.vue` component and no island anywhere. Re-check that claim
  // before extending this entry — it is the whole reason it exists.
  // Only `nuxt` is listed: the same advisory surfaces on
  // `@nuxt/nitro-server` too, but at moderate, so it never reaches this
  // gate — and listing it anyway trips the stale-entry check below,
  // which is how this comment came to exist.
  nuxt: 'needs @nuxtjs/i18n v10; no .server.vue or island in the codebase'
}

const FAIL_AT = new Set(['high', 'critical'])

const result = spawnSync('npm', ['audit', '--json'], {
  encoding: 'utf-8',
  maxBuffer: 64 * 1024 * 1024
})

let report
try {
  report = JSON.parse(result.stdout)
} catch {
  console.error('audit-gate: could not parse `npm audit --json` output')
  console.error(result.stdout?.slice(0, 2000) ?? '', result.stderr ?? '')
  process.exit(2)
}

const entries = Object.entries(report.vulnerabilities ?? {})
const gating = entries.filter(([, v]) => FAIL_AT.has(v.severity))
const unlisted = gating.filter(([name]) => !(name in ALLOWED))

for (const [name, v] of gating) {
  const note = name in ALLOWED ? `allowed — ${ALLOWED[name]}` : 'NOT ALLOWED'
  console.log(`${v.severity.padEnd(8)} ${name.padEnd(28)} ${note}`)
}

// An exception that outlives its advisory is an exception nobody
// reviews, so a stale entry fails just as loudly as a new advisory.
const stale = Object.keys(ALLOWED).filter(
  name => !gating.some(([gatingName]) => gatingName === name)
)
if (stale.length) {
  console.error(
    `\naudit-gate: these are allowlisted but no longer reported at high/critical — `
    + `remove them from scripts/audit-gate.mjs: ${stale.join(', ')}`
  )
  process.exit(1)
}

if (unlisted.length) {
  console.error(
    `\naudit-gate: ${unlisted.length} unlisted high/critical advisor${
      unlisted.length === 1 ? 'y' : 'ies'
    }: ${unlisted.map(([n]) => n).join(', ')}\n`
    + `Fix them, or add an entry with a reason if the fix is genuinely unreachable.`
  )
  process.exit(1)
}

console.log(`\naudit-gate: no unlisted high/critical advisories.`)
