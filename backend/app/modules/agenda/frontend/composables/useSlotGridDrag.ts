/**
 * useSlotGridDrag — pointer-driven drag for the week and day grids.
 *
 * Both grids are the same thing with a different column axis (days vs
 * professionals), and both carried a near-identical copy of this logic
 * built on `mousedown` plus document-level `mousemove`. Chrome on Android
 * emits mouse events only as compatibility events *after* the finger
 * lifts, so none of it tracked on a tablet: no create, no move, no
 * resize. This is one Pointer Events implementation for mouse, finger
 * and stylus alike.
 *
 * ## Fine pointer (mouse, trackpad)
 *
 * Unchanged: press and drag starts immediately. Press on an empty cell
 * and drag down to size a new appointment; press and release without
 * moving is a click on the slot.
 *
 * ## Coarse pointer (finger)
 *
 * A finger cannot hover and a press is ambiguous with a scroll, so the
 * grid uses select-then-drag, the pattern mobile calendars settled on:
 *
 * - Tap an appointment  → open it.
 * - Long-press (300 ms) → select it. The block lifts and grows handles.
 * - Drag a selected block → move it. Drag its handle → resize it.
 * - Tap an empty cell    → create there (no drag; see below).
 * - Tap elsewhere        → deselect.
 *
 * Selection is what makes this work at all. `touch-action: none` is the
 * only way to stop the browser scrolling instead of dragging, and
 * applying it to every block would make the grid unscrollable wherever
 * appointments sit. Applied only while a block is *selected*, the grid
 * scrolls normally until the user has said which block they mean.
 *
 * Drag-to-size on an empty cell is deliberately not offered by touch:
 * it would need `touch-action: none` across the whole canvas, which
 * costs scrolling everywhere to save one modal field. A tap creates at
 * the default duration instead.
 */
import type { Ref } from 'vue'

/** A drag in progress on an existing appointment. */
export interface AppointmentDragState {
  type: 'move' | 'resize'
  appointmentId: string
  startX: number
  startY: number
  originalTop: number
  originalHeight: number
  originalColumnIndex: number
  currentColumnIndex: number
  currentTop: number
  currentHeight: number
}

/** A drag in progress on empty space, sizing a new appointment. */
export interface CreateDragState {
  columnIndex: number
  startSlot: number
  currentSlot: number
  startY: number
}

export interface SlotGridDragOptions {
  /** Pixel height of one slot. Read live — density can change it. */
  slotHeight: () => number
  /** Highest addressable slot index, i.e. slots per day minus one. */
  maxSlotIndex: () => number
  /** Number of data columns (days, or professionals). */
  columnCount: () => number
  /**
   * Columns rendered before the data columns — the time gutter. Used to
   * turn a horizontal delta into a column delta.
   */
  gutterColumns: number
  /** The scroll container, measured to size a column. */
  containerRef: Ref<HTMLElement | null>
  /** Committed when a create-drag covered more than one slot. */
  onCreateRange: (columnIndex: number, startSlot: number, endSlot: number) => void
  /** Committed when a press on empty space did not turn into a drag. */
  onCreatePoint: (columnIndex: number, slot: number) => void
  onMove: (appointmentId: string, columnIndex: number, startSlot: number, endSlot: number) => void
  onResize: (appointmentId: string, endSlot: number) => void
}

/** How long a finger must rest on a block before it is selected. */
const LONG_PRESS_MS = 300
/** Movement that cancels a pending long press — the user is scrolling. */
const LONG_PRESS_SLOP_PX = 10
/** Movement past which a drag suppresses the click that follows it. */
const DRAG_SLOP_PX = 5

export function useSlotGridDrag(options: SlotGridDragOptions) {
  const { isTouch } = useDevice()

  const dragState = ref<AppointmentDragState | null>(null)
  const createDragState = ref<CreateDragState | null>(null)

  /**
   * The appointment a finger has long-pressed. Null with a mouse, which
   * needs no selection step. Drives `touch-action: none` on the block.
   */
  const selectedId = ref<string | null>(null)

  const hasMoved = ref(false)
  const wasDragging = ref(false)

  let longPressTimer: ReturnType<typeof setTimeout> | null = null
  let longPressOrigin: { x: number, y: number } | null = null
  let activePointerId: number | null = null
  let activeElement: HTMLElement | null = null

  /**
   * Swallow the click the browser fires after a gesture that was not a
   * plain tap. `wasDragging` is what the components check before opening
   * an appointment.
   */
  function suppressNextClick() {
    wasDragging.value = true
    setTimeout(() => {
      wasDragging.value = false
    }, 300)
  }

  function cancelLongPress() {
    if (longPressTimer !== null) {
      clearTimeout(longPressTimer)
      longPressTimer = null
    }
    longPressOrigin = null
  }

  function releasePointer() {
    if (activeElement && activePointerId !== null && activeElement.hasPointerCapture(activePointerId)) {
      activeElement.releasePointerCapture(activePointerId)
    }
    activePointerId = null
    activeElement = null
  }

  /**
   * Capture the pointer on the element that started the gesture, so the
   * drag keeps tracking when the finger leaves the block — which it
   * always does, since blocks are ~28 px tall.
   */
  function capture(event: PointerEvent) {
    const el = event.currentTarget as HTMLElement | null
    if (!el) return
    activePointerId = event.pointerId
    activeElement = el
    el.setPointerCapture(event.pointerId)
  }

  function snapSlots(px: number): number {
    return Math.round(px / options.slotHeight())
  }

  // ---------------------------------------------------------------- create

  function onCellPointerDown(columnIndex: number, slot: number, event: PointerEvent) {
    if (dragState.value) return

    // A finger creates by tapping, not by dragging: sizing here would
    // need touch-action: none over the whole grid and cost scrolling.
    if (isTouch.value) {
      selectedId.value = null
      return
    }

    event.preventDefault()
    capture(event)
    createDragState.value = {
      columnIndex,
      startSlot: slot,
      currentSlot: slot,
      startY: event.clientY
    }
  }

  // ------------------------------------------------------------ move/resize

  function beginAppointmentDrag(
    type: 'move' | 'resize',
    appointmentId: string,
    columnIndex: number,
    startSlot: number,
    endSlot: number,
    event: PointerEvent
  ) {
    const h = options.slotHeight()
    const height = Math.max(1, endSlot - startSlot) * h
    dragState.value = {
      type,
      appointmentId,
      startX: event.clientX,
      startY: event.clientY,
      originalTop: startSlot * h,
      originalHeight: height,
      originalColumnIndex: columnIndex,
      currentColumnIndex: columnIndex,
      currentTop: startSlot * h,
      currentHeight: height
    }
    capture(event)
  }

  function onAppointmentPointerDown(
    type: 'move' | 'resize',
    appointmentId: string,
    columnIndex: number,
    startSlot: number,
    endSlot: number,
    event: PointerEvent
  ) {
    event.stopPropagation()

    if (!isTouch.value) {
      event.preventDefault()
      beginAppointmentDrag(type, appointmentId, columnIndex, startSlot, endSlot, event)
      return
    }

    // Already selected: the user has committed to this block, so a press
    // is a drag. `touch-action: none` is in place by now, so the browser
    // will not steal the gesture for a scroll.
    if (selectedId.value === appointmentId) {
      event.preventDefault()
      beginAppointmentDrag(type, appointmentId, columnIndex, startSlot, endSlot, event)
      return
    }

    // Not selected yet: arm a long press, but do not preventDefault —
    // this press may still turn out to be a scroll, and stealing it
    // would freeze the grid.
    longPressOrigin = { x: event.clientX, y: event.clientY }
    longPressTimer = setTimeout(() => {
      longPressTimer = null
      selectedId.value = appointmentId
      // The release that follows still fires a click, which would open
      // the appointment the user was only trying to pick up.
      suppressNextClick()
    }, LONG_PRESS_MS)
  }

  // ------------------------------------------------------------------ move

  function onPointerMove(event: PointerEvent) {
    if (longPressOrigin) {
      const moved = Math.hypot(event.clientX - longPressOrigin.x, event.clientY - longPressOrigin.y)
      if (moved > LONG_PRESS_SLOP_PX) cancelLongPress()
    }

    const h = options.slotHeight()

    if (createDragState.value) {
      const deltaY = event.clientY - createDragState.value.startY
      const slotDelta = Math.floor(deltaY / h)
      createDragState.value.currentSlot = Math.max(
        createDragState.value.startSlot,
        Math.min(options.maxSlotIndex(), createDragState.value.startSlot + slotDelta)
      )
      return
    }

    const state = dragState.value
    if (!state) return

    const deltaY = event.clientY - state.startY
    const deltaX = event.clientX - state.startX

    if (Math.abs(deltaY) > DRAG_SLOP_PX || Math.abs(deltaX) > DRAG_SLOP_PX) {
      hasMoved.value = true
    }

    if (state.type === 'resize') {
      const newHeight = Math.max(h, state.originalHeight + deltaY)
      state.currentHeight = snapSlots(newHeight) * h
      return
    }

    const newTop = Math.max(0, state.originalTop + deltaY)
    const maxSlots = options.maxSlotIndex() + 1 - snapSlots(state.currentHeight)
    state.currentTop = Math.min(snapSlots(newTop), maxSlots) * h

    const container = options.containerRef.value
    const columns = options.columnCount()
    if (container && columns > 1) {
      const columnWidth = container.offsetWidth / (columns + options.gutterColumns)
      const columnDelta = Math.round(deltaX / columnWidth)
      state.currentColumnIndex = Math.max(
        0,
        Math.min(columns - 1, state.originalColumnIndex + columnDelta)
      )
    }
  }

  // ------------------------------------------------------------------- end

  function onPointerUp() {
    cancelLongPress()
    releasePointer()

    const h = options.slotHeight()

    if (createDragState.value) {
      const { columnIndex, startSlot, currentSlot } = createDragState.value
      createDragState.value = null
      if (currentSlot > startSlot) {
        options.onCreateRange(columnIndex, startSlot, currentSlot + 1)
      } else {
        options.onCreatePoint(columnIndex, startSlot)
      }
      return
    }

    // Suppress the click the browser fires after a drag, so releasing a
    // moved appointment does not also open it.
    if (hasMoved.value) suppressNextClick()
    hasMoved.value = false

    const state = dragState.value
    dragState.value = null
    if (!state) return

    const startSlot = snapSlots(state.originalTop)

    if (state.type === 'resize') {
      options.onResize(state.appointmentId, startSlot + snapSlots(state.currentHeight))
      return
    }

    const newStartSlot = snapSlots(state.currentTop)
    const durationSlots = snapSlots(state.currentHeight)
    options.onMove(
      state.appointmentId,
      state.currentColumnIndex,
      newStartSlot,
      newStartSlot + durationSlots
    )
  }

  function onPointerCancel() {
    cancelLongPress()
    releasePointer()
    createDragState.value = null
    dragState.value = null
    hasMoved.value = false
  }

  /** Tap on empty space clears the touch selection. */
  function clearSelection() {
    selectedId.value = null
  }

  onUnmounted(() => {
    cancelLongPress()
    releasePointer()
  })

  return {
    dragState,
    createDragState,
    selectedId,
    wasDragging,
    isTouch,
    onCellPointerDown,
    onAppointmentPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
    clearSelection
  }
}
