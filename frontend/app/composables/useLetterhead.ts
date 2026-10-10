import type { ApiResponse } from '~/types'

/**
 * The letterheads of what the clinic prints: the clinical record, the
 * consent letters, the blank health questionnaire.
 *
 * One of the clinic's own and one per professional who wants theirs. A
 * document carries the letterhead of the professional it answers to, or
 * the clinic's when they have none — never another doctor's. Nobody picks
 * one by hand when printing. Whoever runs the clinic's settings manages
 * them all; each professional may set up their own.
 */
export interface LetterheadWords {
  /** Replaces the clinic's name when set. */
  heading: string | null
  /** A line of its owner's: the professional and licence, a speciality. */
  subheading: string | null
  show_address: boolean
  show_contact: boolean
}

export interface Letterhead extends LetterheadWords {
  /** Whose it is: null is the clinic's own. */
  professional_id: string | null
  has_logo: boolean
}

/** What the acting account may set up for itself. */
export interface OwnLetterhead {
  /** Null: this account is not one of the clinic's professionals. */
  professional_id: string | null
  suggested_subheading: string | null
  letterhead: Letterhead | null
}

const URL_BASE = '/api/v1/auth/clinic/settings/letterheads'

/** The path segment that names a letterhead's owner. */
function owner(professionalId: string | null): string {
  return professionalId ?? 'clinic'
}

export function useLetterhead() {
  const api = useApi()

  async function list(): Promise<Letterhead[]> {
    return (await api.get<ApiResponse<Letterhead[]>>(URL_BASE)).data
  }

  /** The acting professional's own letterhead, if they are one. */
  async function mine(): Promise<OwnLetterhead> {
    return (await api.get<ApiResponse<OwnLetterhead>>(`${URL_BASE}/mine`)).data
  }

  /** Created on first save. */
  async function save(professionalId: string | null, words: LetterheadWords): Promise<Letterhead> {
    return (await api.put<ApiResponse<Letterhead>>(`${URL_BASE}/${owner(professionalId)}`, words)).data
  }

  async function remove(professionalId: string | null): Promise<void> {
    await api.del(`${URL_BASE}/${owner(professionalId)}`)
  }

  /** The logo as an object URL for a preview, or null when there is none. */
  async function logoUrl(professionalId: string | null): Promise<string | null> {
    try {
      const blob = await api.$api<Blob>(`${URL_BASE}/${owner(professionalId)}/logo`, { responseType: 'blob' })
      return URL.createObjectURL(blob)
    } catch {
      return null
    }
  }

  async function uploadLogo(professionalId: string | null, file: File): Promise<void> {
    const form = new FormData()
    form.append('file', file)
    await api.put(`${URL_BASE}/${owner(professionalId)}/logo`, form)
  }

  async function removeLogo(professionalId: string | null): Promise<void> {
    await api.del(`${URL_BASE}/${owner(professionalId)}/logo`)
  }

  return { list, mine, save, remove, logoUrl, uploadLogo, removeLogo }
}
