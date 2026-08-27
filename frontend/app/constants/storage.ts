export const STORAGE_KEYS = {
  LOCALE: 'dentalpin:locale',
  DENSITY: 'ui:density',
  POINTER: 'ui:pointer',
  onboardingDismissed: (clinicId: string) =>
    `dentalpin.settings.onboarding.dismissed:${clinicId}`
} as const
