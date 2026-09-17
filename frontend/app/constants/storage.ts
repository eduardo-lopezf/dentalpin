export const STORAGE_KEYS = {
  LOCALE: 'dentalpin:locale',
  DENSITY: 'ui:density',
  POINTER: 'ui:pointer',
  // A cookie, not localStorage: every tab shares it, and the server reads
  // it to refuse rendering a page for a session that went idle.
  LAST_ACTIVITY: 'session:last-activity',
  onboardingDismissed: (clinicId: string) =>
    `dentalpin.settings.onboarding.dismissed:${clinicId}`
} as const
