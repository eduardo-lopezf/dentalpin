import { loginLocation } from '~/utils/session'

// Pages still name this, but `auth.global.ts` runs first and has already
// redirected anyone it would stop — including idle sessions. Kept in step
// so the two never disagree about where login sends someone back to.
export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuth()

  // Initialize auth state
  await auth.init()

  // Public routes that don't require authentication
  const publicRoutes = ['/login']
  const isPublicRoute = publicRoutes.some(route => to.path.startsWith(route))

  if (!auth.isAuthenticated.value && !isPublicRoute) {
    return navigateTo(loginLocation(to.fullPath))
  }

  if (auth.isAuthenticated.value && to.path === '/login') {
    // Already authenticated, redirect to home
    return navigateTo('/')
  }
})
