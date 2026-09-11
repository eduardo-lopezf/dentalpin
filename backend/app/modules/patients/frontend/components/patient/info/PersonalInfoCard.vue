<script setup lang="ts">
/**
 * PersonalInfoCard — who this patient is.
 *
 * Laid out like `ProfessionalProfileModal`: a tinted band, the portrait
 * sitting on its edge, and the facts as a mosaic of tiles rather than a
 * definition list. A list reads top to bottom and makes you scan for the
 * one line you came for; tiles let the eye land on it directly.
 *
 * The name is the card's heading — the page header above already names
 * the patient, but a card that opens with "Datos personales" and then
 * repeats the name in its body was two titles for one thing.
 *
 * Same fields as before, none added, none dropped: birth date always
 * shows (its absence is itself clinically relevant), the rest only when
 * filled, so a sparse record stays short instead of becoming a grid of
 * dashes.
 */
import type { PatientExtended } from '~~/app/types'
import { formatDateOnly } from '~~/app/utils/date'
import { computeAge } from '../../../utils/medicalSnapshot'

interface Props {
  patient: PatientExtended
  canEdit: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{ edit: [] }>()

const { t, locale } = useI18n()

const age = computed(() => computeAge(props.patient.date_of_birth))

const initials = computed(() => {
  const first = props.patient.first_name?.[0] ?? ''
  const last = props.patient.last_name?.[0] ?? ''
  return (first + last).toUpperCase()
})

const statusColor = computed<'success' | 'neutral'>(() =>
  props.patient.status === 'active' ? 'success' : 'neutral'
)

const birthDisplay = computed(() => {
  // `formatDateOnly`, not `formatPatientDate`: `date_of_birth` is a DATE
  // column, and parsing it with `new Date()` lands on UTC midnight — which
  // west of Greenwich prints the day before. This card said 11/03/1985
  // while the edit form right next to it said 12/03/1985.
  const formatted = formatDateOnly(
    props.patient.date_of_birth,
    locale.value === 'en' ? 'en-US' : 'es-ES',
    { day: '2-digit', month: '2-digit', year: 'numeric' }
  )
  if (!formatted) return null
  if (age.value === null) return formatted
  return t('patients.personalInfo.birthWithAge', { date: formatted, age: age.value })
})

const documentDisplay = computed(() => {
  if (!props.patient.national_id) return null
  const type = props.patient.national_id_type?.toUpperCase() ?? ''
  return type ? `${type}: ${props.patient.national_id}` : props.patient.national_id
})

const genderLabel = computed(() => {
  if (!props.patient.gender) return null
  return props.patient.gender === 'male'
    ? t('patients.gender.male')
    : props.patient.gender === 'female'
      ? t('patients.gender.female')
      : null
})

const tiles = computed(() => {
  const out: { icon: string, label: string, value: string }[] = [
    {
      icon: 'i-lucide-cake',
      label: t('patients.dateOfBirth'),
      value: birthDisplay.value ?? '—'
    }
  ]
  if (genderLabel.value) {
    out.push({
      icon: 'i-lucide-user-2',
      label: t('patients.gender.label'),
      value: genderLabel.value
    })
  }
  if (documentDisplay.value) {
    out.push({
      icon: 'i-lucide-id-card',
      label: t('patients.nationalId'),
      value: documentDisplay.value
    })
  }
  if (props.patient.profession) {
    out.push({
      icon: 'i-lucide-briefcase',
      label: t('patients.profession'),
      value: props.patient.profession
    })
  }
  if (props.patient.workplace) {
    out.push({
      icon: 'i-lucide-building-2',
      label: t('patients.workplace'),
      value: props.patient.workplace
    })
  }
  return out
})
</script>

<template>
  <UCard
    role="region"
    aria-labelledby="personal-info-title"
    class="overflow-hidden"
    :ui="{ body: 'p-0 sm:p-0' }"
  >
    <!-- Identity band. The tint gives the portrait an edge to sit against;
         on a plain white sheet a round image reads as a stray element
         rather than the subject of the card. -->
    <div class="relative">
      <div class="h-20 bg-[var(--color-primary-soft)]" />

      <UButton
        v-if="canEdit"
        variant="soft"
        color="neutral"
        icon="i-lucide-pencil"
        size="sm"
        class="absolute right-3 top-3"
        :aria-label="t('patients.editDemographics')"
        @click="emit('edit')"
      >
        <span class="hidden lg:inline">{{ t('common.edit') }}</span>
      </UButton>

      <div class="-mt-10 flex flex-col items-center px-4 sm:px-6">
        <img
          v-if="patient.photo_url"
          :src="patient.photo_url"
          :alt="`${patient.first_name} ${patient.last_name}`"
          class="h-20 w-20 rounded-full object-cover ring-4 ring-[var(--color-surface)] shadow-token-md"
        >
        <div
          v-else
          class="flex h-20 w-20 items-center justify-center rounded-full bg-surface-muted text-h1 text-muted ring-4 ring-[var(--color-surface)] shadow-token-md"
        >
          {{ initials }}
        </div>

        <h2
          id="personal-info-title"
          class="mt-3 text-h1 text-default text-center text-pretty break-words"
        >
          {{ patient.first_name }} {{ patient.last_name }}
        </h2>

        <div class="mt-2 flex flex-wrap items-center justify-center gap-2">
          <UBadge
            v-if="age !== null"
            color="neutral"
            variant="subtle"
          >
            {{ t('patients.personalInfo.ageLabel', { age }) }}
          </UBadge>
          <UBadge
            :color="statusColor"
            variant="subtle"
          >
            {{ patient.status === 'active' ? t('patients.status.active') : t('patients.status.archived') }}
          </UBadge>
        </div>
      </div>
    </div>

    <div class="px-4 sm:px-6 pb-5 pt-5">
      <!-- Two columns where there is room, one where there is not. A last
           tile landing on an odd position takes the whole row rather than
           leaving a hole beside it. -->
      <dl class="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:[&>*:nth-child(odd):last-child]:col-span-2">
        <div
          v-for="tile in tiles"
          :key="tile.label"
          class="flex items-start gap-3 rounded-token-lg border border-subtle bg-surface-muted px-4 py-3"
        >
          <UIcon
            :name="tile.icon"
            class="mt-0.5 h-5 w-5 shrink-0 text-subtle"
            aria-hidden="true"
          />
          <div class="min-w-0">
            <dt class="text-caption text-subtle">
              {{ tile.label }}
            </dt>
            <dd class="text-ui text-default break-words">
              {{ tile.value }}
            </dd>
          </div>
        </div>
      </dl>

      <!-- Its own `dl`: `dt`/`dd` are only valid inside one, and notes sit
           outside the tile grid because they run long. -->
      <dl
        v-if="patient.notes"
        class="mt-3 rounded-token-lg border border-subtle bg-surface-muted px-4 py-3"
      >
        <dt class="text-caption text-subtle">
          {{ t('patients.notes') }}
        </dt>
        <dd class="mt-1 text-body text-default whitespace-pre-wrap break-words">
          {{ patient.notes }}
        </dd>
      </dl>
    </div>
  </UCard>
</template>
