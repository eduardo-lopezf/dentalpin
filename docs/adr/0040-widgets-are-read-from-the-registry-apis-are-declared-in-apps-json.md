# 0040 — Widgets are read from the slot registry; APIs are declared in `apps.json`

- **Status:** accepted
- **Date:** 2026-10-02
- **Deciders:** Eduardo (maintainer)
- **Tags:** apps, frontend, integrations

> **Update 2026-10-03:** a second API is declared: **WhatsApp**, `planned`, on the Communications App (`notifications` + `whatsapp_kapso`) rather than on Recalls, because Agenda reminders and budgets would use the same channel.

> **Update 2026-10-03:** the Widgets page groups widgets by App, in catalog order. Patients contributes four: recent patients (home), medical history and quick actions (patient summary) and medical alerts (patient header). Anything a widget's example renders — a nested slot included — has to honour `useWidgetPreview()`; the recall button inside quick actions did not.

> **Update 2026-10-03:** Widgets and APIs were tabs of the Apps page. They are now pages of their own in the Settings *Apps* section (`/settings/widgets`, `/settings/apis`), beside Apps. The decision below is unchanged.

## Context

Settings → Apps is to show three things about each App: the App itself,
the **widgets** it contributes to other screens, and the **APIs** — the
outside services it can connect to. `backend/apps.json` already lists
the Apps ([ADR 0038](0038-apps-json-switches-apps-for-the-whole-deployment.md)).
The question is whether widgets and APIs belong in that file too.

They are different kinds of thing. A widget is code: a component a
module registers into a slot from its `slots.client.ts`. It already
exists, with an id, a place and a permission, the moment the layer
loads. An API is a decision: whether this deployment connects Agenda to
Google Calendar. Nothing in the code says so until someone decides.

## Decision

**A widget is described where it is registered. An API is declared in
`apps.json`.**

- **Widgets.** A slot registration marked `widget: true`, with a
  `labelKey` (and optionally a `descriptionKey`), is a widget, and
  Settings → Apps lists it. The flag is explicit because a label alone
  is not enough: tabs and settings pages carry one too. Its id starts with the module that registered it, which ties it
  to an App. The list is read from the slot registry at run time, and
  each widget is shown with an example: the real component, rendered
  `inert` and fed **made-up data**. The catalog marks the subtree as a
  preview (`provideWidgetPreview`); whatever fetches a widget's data
  asks `useWidgetPreview()` and returns samples instead of calling the
  API, in state of its own. Widgets are not switched on
  or off; they follow their App and their permission, as before.
- **APIs.** Each App in `apps.json` may list `apis`, each with a `name`
  and a `status`: `planned`, `enabled` or `disabled`. `planned` means
  listed and nothing more — there is no integration behind it, so
  editing the file cannot switch it on. Agenda lists `google_calendar`
  as `planned`.
- **No secret goes in `apps.json`.** It is a committed file. Credentials
  for an API belong in the environment or the database, and the egress
  it implies is still declared in the module manifest
  ([ADR 0027](0027-egress-is-declared-in-the-manifest.md)).

## Consequences

### Good

- Widgets cannot drift: there is one definition, the registration, and
  the catalog is whatever is registered. A widget written tomorrow
  appears by gaining a label.
- An API's switch sits beside its App's, in the one file an operator
  already edits.

### Bad / accepted trade-offs

- **The widget list is whatever the frontend loaded.** The backend does
  not know it, so there is no API for it and nothing can be decided
  about a widget server-side.
- **Each widget's data source has to know about previews.** A widget
  whose composable does not check `useWidgetPreview()` shows the
  clinic's real data in the catalog, and makes real requests. Agenda's
  five are covered; a new widget needs its own samples.
- **The made-up data is a second thing to keep plausible.** It lives
  beside the module (`agenda/frontend/utils/previewSamples.ts`) and has
  to keep the shape of the real response.
- **Preview state must not be the shared state.** `useHomeAgenda` keeps
  the dashboard's day in global state; the preview branch returns refs
  of its own, or the fiction would show on the real Home.
- If widgets ever become switchable, the *switch* (a status keyed by
  widget id) would go in `apps.json`; the definition would stay in the
  registration.

## Alternatives considered

- **Declare widgets in `apps.json` too.** A second inventory of things
  the code already defines, to be kept in step by hand, with nothing to
  gain while they cannot be switched.
- **Live data in the examples** — what this ADR first chose. Truthful,
  but a clinic with no appointments today saw five empty states, and
  the catalog showed patients' names where nobody expects them.
- **Static mock-ups as examples.** A second rendering of each widget to
  maintain, free to disagree with the real one. Feeding the real
  component sample data keeps one rendering.

## How to verify the rule still holds

- `backend/tests/test_app_catalog.py` — API statuses are validated, an
  API is listed once per App, and Agenda ships Google Calendar as
  `planned`.
- `frontend/tests/e2e/settings-apps.spec.ts` — the Apps page has no tabs,
  Agenda's five widgets on `/settings/widgets`, and the Google Calendar
  card on `/settings/apis`.

## References

- `backend/apps.json`, `backend/app/core/plugins/apps.py`
- `frontend/app/pages/settings/{apps,widgets,apis}/index.vue`
- `frontend/app/components/settings/modules/WidgetCard.vue`, `ApiCard.vue`
- `frontend/app/composables/useModuleSlots.ts` (`listSlotEntries`)
- `backend/app/modules/agenda/frontend/plugins/slots.client.ts`
