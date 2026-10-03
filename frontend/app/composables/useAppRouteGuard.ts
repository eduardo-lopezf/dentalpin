import { appRouteFor } from '~/config/appRoutes'

/**
 * Sends a visit to a disabled App's page back home, with a notice.
 *
 * Runs in the default layout rather than as route middleware: it needs
 * the active-module list, which `useModules` loads through `useApi`, and
 * that reaches `useI18n` — callable from a component's setup, not from
 * middleware. Client-only, so the notice is actually seen: a server
 * redirect would land the user on the dashboard with no explanation.
 */
export function useAppRouteGuard(): void {
  if (!import.meta.client) return

  const route = useRoute()
  const { active, isActive } = useModules()
  const toast = useToast()
  const { t } = useI18n()

  watch(
    [() => route.path, active],
    () => {
      // Not loaded yet: wait. The watcher runs again when it arrives.
      if (active.value === null) return
      const hit = appRouteFor(route.path)
      if (!hit || isActive(hit.module)) return

      toast.add({
        title: hit.noticeKey
          ? t(hit.noticeKey)
          : t('settings.apps.notEnabled', { name: t(`settings.apps.catalog.${hit.app}.title`) }),
        color: 'warning'
      })
      navigateTo('/', { replace: true })
    },
    { immediate: true }
  )
}
