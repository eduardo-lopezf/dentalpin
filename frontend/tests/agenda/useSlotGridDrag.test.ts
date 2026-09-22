import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
// Relative path, same reason as calculateOverlapGroups.test.ts: Nuxt
// aliases would need the full Nuxt env and the /module_layers/ symlink
// only exists inside Docker.
import { useSlotGridDrag } from '../../../backend/app/modules/agenda/frontend/composables/useSlotGridDrag'

// A finger, not a mouse: the long press only exists on the touch path.
mockNuxtImport('useDevice', () => () => ({ isTouch: ref(true) }))
// Called bare here, with no component to unmount: the cleanup is not what
// is under test, and Vue would warn on every call.
mockNuxtImport('onUnmounted', () => () => {})

function grid() {
  return useSlotGridDrag({
    slotHeight: () => 28,
    maxSlotIndex: () => 47,
    columnCount: () => 7,
    gutterColumns: 1,
    containerRef: ref(null),
    onCreateRange: vi.fn(),
    onCreatePoint: vi.fn(),
    onMove: vi.fn(),
    onResize: vi.fn()
  })
}

function press(): PointerEvent {
  return {
    clientX: 100,
    clientY: 100,
    pointerId: 1,
    currentTarget: null,
    stopPropagation: vi.fn(),
    preventDefault: vi.fn()
  } as unknown as PointerEvent
}

const INTENT = {
  type: 'move' as const,
  appointmentId: 'apt-1',
  columnIndex: 0,
  startSlot: 4,
  endSlot: 6
}

describe('long press on an appointment', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  // The click that follows the release is what opens the appointment.
  // Its suppression used to start when the press registered and last
  // 300 ms, so a finger that simply stayed down a little longer — the
  // natural way to long-press — opened the appointment it had selected.
  it('swallows the release click however long the finger was held', () => {
    const g = grid()
    g.onAppointmentPointerDown(INTENT, press())
    vi.advanceTimersByTime(300)
    expect(g.selectedId.value).toBe('apt-1')

    vi.advanceTimersByTime(1500)
    g.onPointerUp()

    expect(g.wasDragging.value).toBe(true)
  })

  it('lets the next click through once the release has been swallowed', () => {
    const g = grid()
    g.onAppointmentPointerDown(INTENT, press())
    vi.advanceTimersByTime(300)
    g.onPointerUp()
    vi.advanceTimersByTime(300)

    expect(g.wasDragging.value).toBe(false)
  })

  it('leaves a quick tap alone, so it still opens the appointment', () => {
    const g = grid()
    g.onAppointmentPointerDown(INTENT, press())
    vi.advanceTimersByTime(100)
    g.onPointerUp()

    expect(g.selectedId.value).toBeNull()
    expect(g.wasDragging.value).toBe(false)
  })

  it('does not carry a cancelled press into the next gesture', () => {
    const g = grid()
    g.onAppointmentPointerDown(INTENT, press())
    vi.advanceTimersByTime(300)
    // The browser took the gesture over, e.g. for a scroll.
    g.onPointerCancel()
    g.onPointerUp()

    expect(g.wasDragging.value).toBe(false)
  })
})
