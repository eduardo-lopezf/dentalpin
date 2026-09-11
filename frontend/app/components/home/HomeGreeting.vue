<script setup lang="ts">
import { PERMISSIONS } from '~/config/permissions'
import { formatInstant } from '~/utils/date'

const { t, locale } = useI18n()
const { user, clinicTimezone } = useAuth()
const { can } = usePermissions()

// "Good evening" and today's date are the *clinic's* clock, not the server's
// and not the browser's. Reading either one made the server and the client
// disagree — on a night when the two straddled midnight the server sent
// "Buenas noches / jueves 3" and the client expected "Buenas tardes /
// miércoles 2", and that text mismatch corrupted the hydrated DOM until the
// next client-side navigation died with `insertBefore: node is not a child of
// this node` and left a blank page.
//
// Both sides now format the same instant in the same zone, so the markup is
// identical and the header needs no placeholder. The instant is seeded on the
// server and travels in the payload, so hydration cannot land on the far side
// of a minute boundary; ``onMounted`` takes over from there.
const nowIso = useState('home:greeting-now', () => new Date().toISOString())

let intervalId: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  nowIso.value = new Date().toISOString()
  intervalId = setInterval(() => {
    nowIso.value = new Date().toISOString()
  }, 60_000)
})

onBeforeUnmount(() => {
  if (intervalId) clearInterval(intervalId)
})

const now = computed(() => new Date(nowIso.value))

/**
 * The clinic's zone as a formatting option, for the one use below that is
 * not a date format. Everything that *is* one goes through `formatInstant`,
 * which applies the same rule so no caller has to remember it.
 */
const zone = computed<Intl.DateTimeFormatOptions>(() =>
  clinicTimezone.value ? { timeZone: clinicTimezone.value } : {}
)

const greetingKey = computed(() => {
  // Pulls the hour as a number rather than rendering a date, so it cannot go
  // through `formatInstant`. `hourCycle: 'h23'` so it parses as 0–23 in every
  // locale.
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', { ...zone.value, hour: 'numeric', hourCycle: 'h23' })
      .format(now.value)
  )
  if (hour < 6 || hour >= 21) return 'dashboard.greetings.evening'
  if (hour < 13) return 'dashboard.greetings.morning'
  return 'dashboard.greetings.afternoon'
})

const firstName = computed(() => user.value?.first_name?.trim() ?? '')

const title = computed(() => {
  const g = t(greetingKey.value)
  return firstName.value ? `${g}, ${firstName.value}` : g
})

const formattedDate = computed(() =>
  formatInstant(
    nowIso.value,
    locale.value,
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' },
    clinicTimezone.value
  )
)

const canWriteAppointments = computed(() => can(PERMISSIONS.appointments.write))
const canWritePatients = computed(() => can(PERMISSIONS.patients.write))
</script>

<template>
  <PageHeader
    :title="title"
    :subtitle="formattedDate"
  >
    <template #actions>
      <UButton
        v-if="canWritePatients"
        to="/patients?new=1"
        variant="soft"
        color="neutral"
        icon="i-lucide-user-plus"
      >
        {{ t('dashboard.quickActions.newPatient') }}
      </UButton>
      <UButton
        v-if="canWriteAppointments"
        to="/appointments?new=1"
        variant="solid"
        color="primary"
        icon="i-lucide-calendar-plus"
      >
        {{ t('dashboard.quickActions.newAppointment') }}
      </UButton>
    </template>
  </PageHeader>
</template>
