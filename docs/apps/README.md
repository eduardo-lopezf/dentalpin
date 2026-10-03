# Apps

One folder per App of [`backend/apps.json`](../../backend/apps.json): a
`README.md` saying what the App is for, what it does with each
integration off and what happens when it is off itself, and a
`CHANGELOG.md` with the App's own version.

What each App is made of — its tier, modules, the Apps it requires — is
generated, not written here: see the [Apps catalog](../apps-catalog.md).
`generate_catalogs.py --check` fails if an App of `apps.json` has no
folder here.

The code is organised by module, not by App
([ADR 0044](../adr/0044-the-app-organises-the-module-holds-the-code.md)):
an App's modules live side by side in `backend/app/modules/`.
