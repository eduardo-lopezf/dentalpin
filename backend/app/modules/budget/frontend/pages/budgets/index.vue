<script setup lang="ts">
/**
 * Kept alive as a redirect. This list is now the `budget` tab of the
 * host's Finanzas page; the route stays so existing links, bookmarks and
 * anything that still points here keep working.
 */
definePageMeta({
  middleware: 'auth',
  redirect: '/finanzas?tab=budget'
})
</script>

<template>
  <div />
</template>
