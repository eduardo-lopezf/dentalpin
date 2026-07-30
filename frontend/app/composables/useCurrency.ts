// Single source of truth for rendering money in the frontend.
// - Currency comes from `currentClinic.currency` (one clinic = one currency).
// - Locale follows the user's UI language (Intl handles separators/symbols).
//
// Components that render money should call `format()` (or use the `<Money>`
// component, which delegates here). No callsite should hardcode 'EUR' or
// inline `Intl.NumberFormat`.

export function useCurrency() {
  const { currentClinic } = useClinic()
  const { currentLocale } = useLocale()

  function format(amount: number | string | null | undefined): string {
    if (amount == null || amount === '') return '—'
    const value = typeof amount === 'string' ? Number(amount) : amount
    if (Number.isNaN(value)) return '—'
    const currency = currentClinic.value?.currency ?? 'MXN'
    return new Intl.NumberFormat(currentLocale.value, {
      style: 'currency',
      currency
    }).format(value)
  }

  // Bare symbol/code for inline adornments (input suffixes, small badges)
  // where a fully formatted amount doesn't fit next to an editable number.
  // Falls back to the ISO code if Intl can't resolve a symbol.
  const symbol = computed(() => {
    try {
      const parts = new Intl.NumberFormat(currentLocale.value, {
        style: 'currency',
        currency: currentClinic.value?.currency ?? 'MXN'
      }).formatToParts(0)
      return parts.find(p => p.type === 'currency')?.value ?? (currentClinic.value?.currency ?? 'MXN')
    } catch {
      return currentClinic.value?.currency ?? 'MXN'
    }
  })

  return {
    format,
    currency: computed(() => currentClinic.value?.currency ?? 'MXN'),
    symbol
  }
}