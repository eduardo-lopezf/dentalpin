<script setup lang="ts">
/**
 * AppointmentDateNav — the agenda's date navigator.
 *
 * The week, day and kanban views each carried their own copy of this
 * row: three identical sets of prev / today / next buttons plus a date
 * label, stacked under the page header and the filters. On an 800 px
 * tall tablet that third row cost about 7% of the visible day for
 * markup that was the same in all three places.
 *
 * It now lives once, in the page header, and the views render only the
 * grid. Which unit it steps by follows the active view: a week for the
 * weekly grid, a day for the other two.
 */
const props = defineProps<{
  mode: 'week' | 'day'
  weekStart: Date
  date: Date
}>()

const emit = defineEmits<{
  'week-change': [weekStart: Date]
  'date-change': [date: Date]
}>()

const { t, locale } = useI18n()

function mondayOf(date: Date): Date {
  const d = new Date(date)
  const day = d.getDay()
  d.setDate(d.getDate() + (day === 0 ? -6 : 1 - day))
  d.setHours(0, 0, 0, 0)
  return d
}

function step(direction: -1 | 1) {
  if (props.mode === 'week') {
    const next = new Date(props.weekStart)
    next.setDate(next.getDate() + direction * 7)
    emit('week-change', next)
    return
  }
  const next = new Date(props.date)
  next.setDate(next.getDate() + direction)
  emit('date-change', next)
}

function goToday() {
  const today = new Date()
  if (props.mode === 'week') {
    emit('week-change', mondayOf(today))
  } else {
    emit('date-change', today)
  }
}

const label = computed(() => {
  if (props.mode === 'week') {
    const end = new Date(props.weekStart)
    end.setDate(end.getDate() + 6)
    const from = props.weekStart.toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
    const to = end.toLocaleDateString(locale.value, {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
    return `${from} - ${to}`
  }
  return props.date.toLocaleDateString(locale.value, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
})

const isToday = computed(() => {
  if (props.mode === 'week') {
    const thisMonday = mondayOf(new Date())
    return props.weekStart.toDateString() === thisMonday.toDateString()
  }
  return props.date.toDateString() === new Date().toDateString()
})
</script>

<template>
  <div class="flex items-center gap-2 min-w-0">
    <UButton
      variant="outline"
      color="neutral"
      icon="i-lucide-chevron-left"
      :aria-label="t('appointments.previous', 'Anterior')"
      @click="step(-1)"
    />
    <UButton
      variant="outline"
      color="neutral"
      @click="goToday"
    >
      {{ t('appointments.today') }}
    </UButton>
    <UButton
      variant="outline"
      color="neutral"
      icon="i-lucide-chevron-right"
      :aria-label="t('appointments.next', 'Siguiente')"
      @click="step(1)"
    />
    <span
      class="text-h2 capitalize truncate"
      :class="isToday ? 'text-[var(--color-primary-soft-text)]' : 'text-default'"
    >
      {{ label }}
    </span>
  </div>
</template>
