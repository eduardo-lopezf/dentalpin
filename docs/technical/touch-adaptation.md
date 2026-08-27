# Touch adaptation

How DentalPin adapts to being driven by a finger. The rule and its
rationale live in
[ADR 0022](../adr/0022-touch-adaptation-is-capability-driven.md); this is
the working reference for module authors.

## The one-line rule

**Capability decides interaction. Space decides layout. The user-agent
decides nothing.**

## What detects what

| Question | Read | Do not read |
|---|---|---|
| Should targets be finger-sized? | `useDevice().isTouch` | viewport width |
| Is a hover affordance reachable? | `useDevice().hasHover` | viewport width |
| How many columns fit? | `useBreakpoint()`, container queries | pointer kind |
| Should this board stack? | `useDevice().isPortrait` | pointer kind |
| Which browser is this? | `useDevice().browser` — **diagnostics only** | — |

`useDevice()` publishes its findings on the root element, so CSS and the
E2E suite can read them without a JS bridge:

```html
<html data-pointer="coarse" data-orientation="landscape"
      data-ua="Chrome 151 / Android" class="density-touch">
```

`data-ua` exists so that support can open DevTools on a clinic's real
tablet and see what the app concluded. **No layout or interaction
decision may branch on it.**

## The 44 px minimum

Enforced centrally in `frontend/app/assets/css/main.css`, under
`@media (pointer: coarse)`. You do not need to do anything per component:
buttons, links, tabs, selects and text inputs get `min-height: 44px`, and
icon-only controls get `min-width: 44px` too.

Two things to know about that block:

- **It sits outside `@layer utilities` on purpose**, so it outranks
  Tailwind utilities. A `min-h-0` class on your component will *not*
  override it.
- **Hover-revealed actions become visible.** The
  `opacity-0 group-hover:opacity-100` idiom is neutralised, because with
  no hover those actions are otherwise unreachable.

## Opting out: `data-dense`

Some surfaces are not made of buttons. A calendar slot is a unit of time
whose height *is* fifteen minutes; a periodontal cell is a probing site;
a timeline chip's width encodes a duration. Growing them to 44 px would
distort the data, not improve the ergonomics.

Put `data-dense` on a container and everything inside keeps its own
scale, hover-reveal included:

```vue
<!-- data-dense: the grid is a time canvas, not a toolbar. -->
<div data-dense class="min-w-[800px]">
```

Surfaces currently opted out:

| Surface | Why |
|---|---|
| `AppointmentCalendar` week grid | slot height is 15 minutes |
| `AppointmentDailyView` grid | same |
| `TodayTimelineStrip` | chip width encodes appointment duration |
| `PerioArchBlock` table | cells are probing sites, 6 per tooth |

**`data-dense` is a debt marker, not a solution.** It says "this surface
needs a purpose-built touch interaction", and the E2E audit deliberately
skips what is inside it — so opting out buys you no coverage. Use it when
the alternative would corrupt the data the surface is drawing, and pair
it with a plan.

## Density

`useDensity()` returns:

- `density` — the user's preference, `comfortable | compact`, in a cookie.
- `effective` — what actually reaches `<html>`: `touch` whenever a coarse
  pointer is driving, otherwise the preference.
- `isForced` — true while touch is overriding; the density toggle hides
  itself.

The preference is never overwritten, so docking a keyboard and trackpad
returns the user to their compact layout without re-choosing it.

## Testing

The `tablet-landscape` (1280×800) and `tablet-portrait` (800×1280)
Playwright projects run `tests/e2e/tablet-touch.spec.ts` with
`hasTouch: true, isMobile: false` — which is exactly a tablet: a coarse
pointer at laptop width.

```bash
cd frontend && npx playwright test --project=tablet-landscape --project=tablet-portrait
```

The audit test fails if any control outside a `data-dense` surface is
under 44 px on `/`, `/appointments` or `/patients`. Add a route to that
list when you ship a screen that matters on tablet.

One gotcha when writing tablet tests: everything here is computed on the
client at mount, and the dev server hydrates well past the default 5 s
expect timeout on a cold module graph. Wait for `html[data-ua]` — written
by `useDevice`'s mount hook — before asserting.

## Dragging by touch

The agenda's grids and kanban run on Pointer Events, which cover mouse,
finger and stylus in one code path. The gestures differ by pointer kind
because the constraints do:

| Gesture | Mouse | Finger |
|---|---|---|
| Open an appointment | click | tap |
| Move / resize | press and drag | long-press to select, then drag |
| Create | drag over empty slots to size it | tap a slot, set duration in the modal |
| Kanban: move a card | press and drag | long-press, then drag |

Two constraints shape all of it, and they are worth knowing before
changing anything here:

**A press is ambiguous with a scroll.** That is why a finger needs a
long press (300 ms, cancelled by 10 px of movement) before anything is
picked up. A mouse has no such ambiguity and drags immediately.

**`touch-action: none` is the only thing that stops the browser
scrolling instead of dragging**, and it has to be in place *before* the
gesture starts. The grids solve this with selection: the style lands on
the block a long press selected, so the grid stays scrollable everywhere
else. The kanban has no selection concept, so it attaches a non-passive
`touchmove` blocker when the long press fires — which works precisely
because the long press guarantees the finger was still, so no scroll has
been claimed yet.

Drag-to-size on an empty slot is deliberately not offered by touch: it
would need `touch-action: none` across the whole canvas, trading
scrolling everywhere for one field that the modal already has.

`useSlotGridDrag` holds the shared implementation for the week and day
grids, which are the same grid with a different column axis.

## Known gaps

These are not covered yet and are tracked as follow-up work:

- **Appointment quick actions are still hover-revealed.** They sit
  inside a `data-dense` block, where the global hover-reveal override
  does not apply, because an always-visible button lands on the
  patient's name in a 28 px block. Reaching them by touch needs the
  block redesigned — tapping the appointment and using the modal is the
  route today.
- **Periodontal charting is 14 px cells.** Needs a dedicated touch entry
  mode with an on-screen numeric keypad and auto-advance.
- **The agenda spends ~48 px on a date-navigator row** that each of the
  three view components renders for itself. Merging it into the page
  header would return about 7% of the visible day on an 800 px-tall
  screen, and would drop triplicated markup.
