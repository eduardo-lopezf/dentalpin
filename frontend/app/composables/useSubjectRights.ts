/**
 * Exercising a patient's rights over the `/api/v1/privacy` endpoints
 * (ADR 0026).
 *
 * Two things this deliberately does not hide. An **export** returns every
 * module's data on one patient in cleartext, so it is never fetched
 * speculatively — only when someone asks for it, with a reason. And an
 * **erasure** is irreversible, so this composable does not wrap it in
 * anything that could fire from a stray click: the caller supplies the
 * reason and owns the confirmation.
 */
import type { ApiResponse, PaginatedResponse } from '~/types'

export interface SubjectSection {
  module: string
  section: string
  erasable: boolean
  retention_reason: string | null
  rows: Record<string, unknown>[]
}

export interface SubjectExport {
  patient_id: string
  generated_at: string
  sections: SubjectSection[]
}

export interface RetainedSection {
  module: string
  section: string
  reason: string
}

export interface ErasureResult {
  patient_id: string
  request_id: string
  scrubbed: Record<string, number>
  retained: RetainedSection[]
}

export interface SubjectRequest {
  id: string
  patient_id: string
  action: 'export' | 'erasure'
  requested_by: string
  reason: string
  outcome: Record<string, unknown>
  created_at: string
}

export function useSubjectRights() {
  const api = useApi()

  const isWorking = ref(false)
  const error = ref<string | null>(null)

  async function exportPatient(patientId: string, reason: string): Promise<SubjectExport | null> {
    isWorking.value = true
    error.value = null
    try {
      const response = await api.get<ApiResponse<SubjectExport>>(
        `/api/v1/privacy/subjects/${patientId}/export?reason=${encodeURIComponent(reason)}`
      )
      return response.data
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      isWorking.value = false
    }
  }

  async function erasePatient(patientId: string, reason: string): Promise<ErasureResult | null> {
    isWorking.value = true
    error.value = null
    try {
      const response = await api.post<ApiResponse<ErasureResult>>(
        `/api/v1/privacy/subjects/${patientId}/erasure`,
        { reason }
      )
      return response.data
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      isWorking.value = false
    }
  }

  async function listRequests(page = 1, pageSize = 20) {
    isWorking.value = true
    error.value = null
    try {
      return await api.get<PaginatedResponse<SubjectRequest>>(
        `/api/v1/privacy/subjects/requests?page=${page}&page_size=${pageSize}`
      )
    } catch (e) {
      error.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      isWorking.value = false
    }
  }

  /**
   * Hand the export to the operator as a file.
   *
   * A portability response is meant to leave the browser — the patient
   * gets a copy — so the JSON is downloaded rather than only rendered.
   */
  function downloadExport(data: SubjectExport) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `datos-paciente-${data.patient_id}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  return { isWorking, error, exportPatient, erasePatient, listRequests, downloadExport }
}
