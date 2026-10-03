/**
 * The one way another app sends someone to book an appointment.
 *
 * Agenda is an App the deployment can switch off (`backend/apps.json`,
 * ADR 0038). When it is off its pages and its API are gone, so a plain
 * `router.push('/appointments')` from a patient or a recall would land
 * on a screen that cannot load. Going through here says so instead.
 */
export function useAppointmentBooking() {
  const { active, isActive, ensureLoaded } = useModules()
  const toast = useToast()
  const { t } = useI18n()

  // Until the active list has arrived, assume the agenda is there: the
  // API is the real gate, and a control hidden for a moment on every
  // page load is worse than one that occasionally answers with a toast.
  const available = computed(() => active.value === null || isActive('agenda'))

  async function book(query: Record<string, string> = {}): Promise<void> {
    await ensureLoaded()
    if (!available.value) {
      toast.add({ title: t('appointments.unavailable'), color: 'warning' })
      return
    }
    await navigateTo({ path: '/appointments', query })
  }

  return { available, book }
}
