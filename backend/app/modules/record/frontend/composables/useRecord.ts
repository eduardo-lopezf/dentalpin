import type { ApiResponse } from '~~/app/types'

/**
 * The patient's clinical record, composed by the server from the modules
 * that own the data. Types live here, with the module (ADR 0044).
 */
export type RecordEntryStatus = 'active' | 'ended' | 'retracted'

export interface RecordEntry {
  occurred_at: string
  summary: string
  detail: Record<string, unknown>
  status: RecordEntryStatus
  authored_by_professional_id: string | null
  recorded_by_user_id: string | null
  source_table: string | null
  source_id: string | null
}

export interface RecordSection {
  module: string
  name: string
  title_key: string
  category: string
  entries: RecordEntry[]
}

export interface RecordProfessional {
  id: string
  first_name: string
  last_name: string
  license_number: string | null
}

export interface RecordRequirement {
  key: string
  met: boolean
  /** For a requirement met in part: which of its fields are empty. */
  missing: string[]
}

export interface PatientRecord {
  patient_id: string
  composed_at: string
  sections: RecordSection[]
  professionals: RecordProfessional[]
  coverage: RecordRequirement[]
}

export type DisclosurePurpose
  = 'continuity_of_care' | 'patient_copy' | 'authorised_third_party' | 'legal_requirement'

export interface DisclosureRequest {
  purpose: DisclosurePurpose
  recipient_name: string
  evidence?: string
  identity_verified?: boolean
  /** Sections to include, as `module.section`. */
  scope: string[]
  locale: 'es' | 'en'
}

export interface Disclosure {
  id: string
  purpose: DisclosurePurpose
  recipient_name: string
  document_sha256: string
  created_at: string
}

/** How a clinic lays its record out, and what there is to lay out. */
export interface RecordFormat {
  hidden_sections: string[]
  section_order: string[]
  disabled_requirements: string[]
}

export interface RecordFormatOptions extends RecordFormat {
  available_sections: { qualified_name: string, title_key: string, category: string }[]
  requirements: string[]
}

export function useRecord() {
  const api = useApi()
  const auth = useAuth()
  const config = useRuntimeConfig()

  async function compose(patientId: string, includeRetracted = false): Promise<PatientRecord> {
    const query = includeRetracted ? '?include_retracted=true' : ''
    return (await api.get<ApiResponse<PatientRecord>>(`/api/v1/record/patients/${patientId}${query}`)).data
  }

  /**
   * Hand the record over: the server produces the document, stores it as
   * it left and records to whom and why (ADR 0033).
   */
  async function disclose(patientId: string, data: DisclosureRequest): Promise<Disclosure> {
    return (await api.post<ApiResponse<Disclosure>>(`/api/v1/record/patients/${patientId}/disclosures`, data)).data
  }

  /**
   * A tab opened *before* any await, so the popup blocker counts it as
   * part of the tap. Safari (iPad) drops a `window.open` made after a
   * network round-trip.
   */
  function reserveTab(): Window | null {
    return window.open('', '_blank')
  }

  /** The stored document of a disclosure, in the reserved tab or as a download. */
  async function openDocument(disclosureId: string, tab: Window | null): Promise<void> {
    const response = await fetch(
      `${config.public.apiBaseUrl}/api/v1/record/disclosures/${disclosureId}/document`,
      { headers: { Authorization: `Bearer ${auth.accessToken.value}` } }
    )
    if (!response.ok) {
      tab?.close()
      throw new Error('Failed to load the disclosed record')
    }
    const url = URL.createObjectURL(await response.blob())
    if (tab && !tab.closed) {
      tab.location.href = url
    } else {
      const link = document.createElement('a')
      link.href = url
      link.download = `expediente_${disclosureId.slice(0, 8)}.pdf`
      document.body.appendChild(link)
      link.click()
      link.remove()
    }
    // The tab needs the URL until it has read it.
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  async function getFormat(): Promise<RecordFormatOptions> {
    return (await api.get<ApiResponse<RecordFormatOptions>>('/api/v1/record/format')).data
  }

  async function saveFormat(format: RecordFormat): Promise<RecordFormatOptions> {
    return (await api.put<ApiResponse<RecordFormatOptions>>('/api/v1/record/format', format)).data
  }

  return { compose, disclose, reserveTab, openDocument, getFormat, saveFormat }
}
