# 0022 — Touch adaptation is capability-driven, not width- or UA-driven

- **Status:** accepted
- **Date:** 2026-08-27
- **Deciders:** Eduardo
- **Tags:** frontend, design-system, accessibility

## Context

DentalPin is used on tablets in the gabinete and, increasingly, at the
front desk. The UI had three width breakpoints (`useBreakpoint`:
`< 768` mobile, `768–1023` tablet, `>= 1024` desktop) and every touch
accommodation hung off them: `useDensity` forced the comfortable scale
below 1024 px, and the layout collapsed the sidebar only inside the
768–1023 band.

That model misses the device it most needs to serve. A 10–11" tablet in
landscape reports a 1280×800 CSS viewport: as wide as a laptop, so it was
classified `desktop` and got the full mouse UI — compact density
available, hover-only affordances, a 240 px sidebar. The same tablet
rotated to portrait reports 800×1280 and fell into the `tablet` band. So
**rotating the device changed the interaction model**, not just the
layout: controls resized, the sidebar behaviour changed, and gestures
that worked one way round did not work the other.

An audit of `/appointments` at 1280×800 with a coarse pointer found 36 of
36 visible interactive controls below the 44×44 px the design system
already required (`docs/technical/design-system.md` §11).

Width is also the wrong signal in the other direction: a touchscreen PC
at reception has a wide viewport and a finger, and a tablet with a
keyboard folio has a narrow viewport and a trackpad.

## Decision

**Touch adaptation keys on pointer capability. Layout keys on available
space. Neither keys on the user-agent string.**

Concretely:

1. `useDevice()` exposes `isTouch` from `(pointer: coarse)` and
   `hasHover` from `(hover: hover)`. Anything about target size, hover
   affordances or density reads these.
2. Orientation (`isPortrait` / `isLandscape`) decides **layout only** —
   how many columns fit, whether a board stacks. It must never change how
   a gesture behaves. Rotating the tablet is not a mode switch.
3. `useBreakpoint()` keeps its width semantics and stays for layout
   questions. It is no longer a proxy for "is this touch".
4. Nothing branches on `navigator.userAgent`. `useDevice().browser` reads
   `navigator.userAgentData` and is published on `<html data-ua>` for
   field diagnostics; no layout or interaction decision may read it.
5. The 44 px minimum is enforced centrally, in an unlayered
   `@media (pointer: coarse)` block in `main.css`. Surfaces whose cells
   are units of time or anatomy rather than buttons opt out with
   `data-dense` on a container, and take a purpose-built touch
   interaction instead of a bigger box.

## Consequences

### Good

- The 1280×800 landscape tablet — the actual deployment target — is
  handled, and so is the touchscreen PC and the keyboard-docked tablet,
  without any of them being enumerated.
- Rotation is now a pure layout event. The user's muscle memory survives
  it.
- One central rule replaced what would otherwise be a per-component hunt
  across 233 module components: undersized targets outside dense surfaces
  went from 36 to 0 on `/appointments`.
- The user's compact/comfortable preference is preserved rather than
  overwritten while touch is active, so docking a trackpad restores it.

### Bad / accepted trade-offs

- `data-dense` is a real escape hatch that can be misused to silence the
  touch minimums instead of designing for touch. The E2E audit only
  checks controls *outside* dense surfaces, so a component that opts out
  buys itself no coverage — the review question is whether the surface
  genuinely encodes something other than a button.
- The unlayered CSS block outranks Tailwind utility classes by design, so
  `min-h-0` on a component will not override it. `data-dense` is the only
  way out, which is deliberate but surprising the first time.
- On a first-ever visit the server cannot know the pointer kind; the
  cookie is empty, SSR renders the fine-pointer scale, and the touch
  scale lands on mount. Subsequent loads are correct from the first
  paint.
- Chromium reports `(pointer: coarse)` for a stylus-only device the same
  as for a finger, so a pen-driven tablet gets finger-sized targets. That
  is the safe direction to be wrong in.

## Alternatives considered

- **Keep width breakpoints, add a tablet band up to 1366 px** — would
  catch this tablet and break the next one, and still gets the
  touchscreen PC and the docked tablet backwards. Width does not answer
  the question being asked.
- **Sniff the user-agent for Android/iPad** — brittle, needs maintaining
  per device generation, wrong for a docked tablet and for a touchscreen
  PC, and invisible to `@media` so the CSS would need a JS-set class to
  hang off anyway.
- **A manual "touch mode" toggle in settings** — puts a setup step
  between a clinic and a working UI, and gets forgotten on the shared
  tablet that two roles use differently through the day. Detection is
  free and correct; a toggle can still be added later as an override.
- **Per-component tap-target fixes** — 246 `size="xs"` and 214
  `size="sm"` call sites across the modules. It would drift out of date
  from the first new component onward.

## How to verify the rule still holds

- `frontend/tests/e2e/tablet-touch.spec.ts`, run by the
  `tablet-landscape` and `tablet-portrait` Playwright projects, asserts
  that no control outside a `data-dense` surface is under 44 px on `/`,
  `/appointments` and `/patients`, and that the pointer kind and
  orientation reach `<html>`.
- A UA sniff creeping back in:
  `grep -rn "navigator.userAgent" frontend/app backend/app/modules --include="*.vue" --include="*.ts"`
  should only match `useDevice.ts`'s diagnostic fallback.

## References

- `frontend/app/composables/useDevice.ts`
- `frontend/app/composables/useDensity.ts`
- `frontend/app/assets/css/main.css` — "Touch adaptation"
- `docs/technical/touch-adaptation.md`
- `docs/technical/design-system.md` §5, §11
