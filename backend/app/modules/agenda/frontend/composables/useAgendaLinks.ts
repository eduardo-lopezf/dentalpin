/**
 * What the agenda can link an appointment to right now.
 *
 * Patients, professionals and planned treatments belong to other Apps,
 * which the deployment can switch off (ADR 0037, ADR 0038). The agenda
 * books either way; these flags decide whether it offers the picker or
 * says it cannot.
 *
 * Until the active-module list has arrived each flag is true: the API
 * is the real gate, and a picker that vanishes for a moment on every
 * load is worse than one that occasionally answers with an error.
 */
export function useAgendaLinks() {
  const { active, isActive } = useModules()

  const available = (module: string) =>
    computed(() => active.value === null || isActive(module))

  return {
    patientsAvailable: available('patients'),
    professionalsAvailable: available('professionals'),
    treatmentsAvailable: available('treatment_plan')
  }
}
