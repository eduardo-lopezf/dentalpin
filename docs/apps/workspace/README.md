# Espacio de trabajo (`workspace`)

- **Tier:** base  ·  **Version:** 0.1
- **Declared in:** `backend/apps.json`  ·  **Composition and requirements:** [Apps catalog](../../apps-catalog.md)

## What it is for

The App every workspace runs on: the clinic, its users, roles and permissions, sign-in, the shell (menu, home page and its widgets) and Settings. It is the core (`backend/app/core/`) and the host frontend (`frontend/app/`), not a group of modules.

## Modules

None. The core and the host frontend.

## With this App off

It cannot be switched off: the catalog loader refuses a base App that is `disabled`.

## Notes

- Settings → Apps → Espacio de trabajo is its own page. Its first section, *Inicio*, chooses which widgets the home page shows and in what order, per clinic (`clinic.settings.home_layout`).
- It hosts what the other Apps contribute: menu entries, home widgets, settings pages.

## Decisions

- [0043](../../adr/0043-the-workspace-is-the-base-app.md)
- [0041](../../adr/0041-a-screen-hosts-other-apps-through-slots.md)
