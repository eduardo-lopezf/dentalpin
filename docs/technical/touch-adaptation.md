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

## Known gaps

These are not covered yet and are tracked as follow-up work:

- **Agenda drag and drop is mouse-only.** `AppointmentCalendar` and
  `AppointmentDailyView` drive create/move/resize from `mousedown` plus
  document `mousemove`; Chrome on Android emits those only as
  compatibility events after the finger lifts, so the drag never tracks.
  `AppointmentKanbanView` uses HTML5 drag and drop, which Chrome on
  Android does not implement for touch at all. The fix is Pointer Events
  with `setPointerCapture`, plus long-press to disambiguate drag from tap.
- **Appointment quick actions are unreachable on touch.** They are
  hover-revealed inside a `data-dense` block, where the global
  hover-reveal override does not apply — an always-visible button would
  land on top of the patient's name in a 28 px block. Needs the block
  redesigned.
- **Periodontal charting is 14 px cells.** Needs a dedicated touch entry
  mode with an on-screen numeric keypad and auto-advance.
- **Kanban columns do not respond to orientation.** Five columns scroll
  horizontally in both, wasting the height a portrait tablet has.
