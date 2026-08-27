/**
 * Every string the UI can show must exist in both languages.
 *
 * Audit S5: the invoice-series screen shipped 30 Spanish-only keys and
 * the legal-guardian form 23 more, so an English-speaking user got raw
 * key paths on screen — and 19 keys had drifted the other way, which the
 * Spanish-speaking clinic saw. Nothing checked it, so it drifted quietly.
 *
 * Covers the host locales and every module layer's own, including the
 * ones that name their files `<module>-<code>.json`.
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const modulesRoot = resolve(frontendRoot, '..', 'backend', 'app', 'modules')

type Bundle = { name: string, dir: string, files: Record<string, string> }

function flatten(value: unknown, prefix = ''): string[] {
  if (value === null || typeof value !== 'object') return [prefix]
  return Object.entries(value as Record<string, unknown>)
    .flatMap(([key, child]) => flatten(child, prefix ? `${prefix}.${key}` : key))
}

function keysOf(file: string): string[] {
  return flatten(JSON.parse(readFileSync(file, 'utf-8'))).sort()
}

function localeDirs(): Bundle[] {
  const bundles: Bundle[] = [{ name: 'host', dir: join(frontendRoot, 'i18n/locales'), files: {} }]

  for (const entry of readdirSync(modulesRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue
    const dir = join(modulesRoot, entry.name, 'frontend/i18n/locales')
    if (existsSync(dir)) bundles.push({ name: entry.name, dir, files: {} })
  }

  for (const bundle of bundles) {
    for (const file of readdirSync(bundle.dir)) {
      // `en.json` and `notifications-en.json` are both valid layouts —
      // each layer declares its own filenames in its nuxt.config.
      const match = /(?:^|-)(en|es)\.json$/.exec(file)
      if (match) bundle.files[match[1]!] = join(bundle.dir, file)
    }
  }

  return bundles
}

describe('i18n parity', () => {
  const bundles = localeDirs()

  it('finds the host bundle and the module bundles', () => {
    expect(bundles.length).toBeGreaterThan(5)
    expect(bundles[0]!.name).toBe('host')
  })

  it.each(bundles)('$name ships both locales', (bundle) => {
    expect(Object.keys(bundle.files).sort()).toEqual(['en', 'es'])
  })

  it.each(bundles)('$name has the same keys in es and en', (bundle) => {
    const es = keysOf(bundle.files.es!)
    const en = keysOf(bundle.files.en!)

    expect({ missingInEn: es.filter(k => !en.includes(k)) }).toEqual({ missingInEn: [] })
    expect({ missingInEs: en.filter(k => !es.includes(k)) }).toEqual({ missingInEs: [] })
  })
})
