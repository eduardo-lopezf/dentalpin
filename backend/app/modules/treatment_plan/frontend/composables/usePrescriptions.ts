import type { ApiResponse } from '~~/app/types'

export interface Prescription {
  id: string
  patient_id: string
  plan_item_id: string | null
  treatment_label: string | null
  professional_id: string | null
  professional_name: string
  professional_license: string | null
  body: string
  issued_by: string | null
  created_at: string
}

const BASE = '/api/v1/treatment_plan'

/**
 * Prescriptions written from a plan treatment, and their printable PDF.
 */
export function usePrescriptions() {
  const api = useApi()
  const auth = useAuth()
  const config = useRuntimeConfig()

  async function listForItem(planId: string, itemId: string): Promise<Prescription[]> {
    const res = await api.get<ApiResponse<Prescription[]>>(
      `${BASE}/treatment-plans/${planId}/items/${itemId}/prescriptions`
    )
    return res.data
  }

  async function create(
    planId: string,
    itemId: string,
    body: string,
    professionalId: string
  ): Promise<Prescription> {
    const res = await api.post<ApiResponse<Prescription>>(
      `${BASE}/treatment-plans/${planId}/items/${itemId}/prescriptions`,
      { body, professional_id: professionalId }
    )
    return res.data
  }

  /**
   * A tab opened *before* any await, so the popup blocker counts it as
   * part of the tap. Safari (iPad) drops a `window.open` made after a
   * network round-trip.
   */
  function reserveTab(): Window | null {
    return window.open('', '_blank')
  }

  /** Load the PDF into the reserved tab, or download it when there is none. */
  async function openPdf(id: string, locale: string, tab: Window | null): Promise<void> {
    const response = await fetch(
      `${config.public.apiBaseUrl}${BASE}/prescriptions/${id}/pdf?locale=${locale}`,
      { headers: { Authorization: `Bearer ${auth.accessToken.value}` } }
    )
    if (!response.ok) {
      tab?.close()
      throw new Error('Failed to load prescription PDF')
    }
    const url = URL.createObjectURL(await response.blob())
    if (tab && !tab.closed) {
      tab.location.href = url
    } else {
      const link = document.createElement('a')
      link.href = url
      link.download = `receta_${id.slice(0, 8)}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
    }
    // The tab needs the URL until it has read it.
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  return { listForItem, create, reserveTab, openPdf }
}
