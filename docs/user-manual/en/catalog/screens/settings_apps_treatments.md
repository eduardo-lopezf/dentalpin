---
module: catalog
screen: settings_apps_treatments
route: /settings/apps/treatments
related_endpoints:
  - GET /api/v1/catalog/specialty-packs
  - GET /api/v1/catalog/specialty-packs/{key}
  - POST /api/v1/catalog/specialty-packs/{key}/enable
  - POST /api/v1/catalog/specialty-packs/{key}/disable
  - POST /api/v1/catalog/specialty-packs/{key}/restore
related_permissions:
  - catalog.read
  - catalog.admin
related_paths:
  - backend/app/modules/catalog/frontend/pages/settings/apps/treatments.vue
last_verified_commit: 01eb2d1
screenshots:
  - catalog/settings_apps_treatments-subareas.png
---

# Treatments settings: specialties

**Settings → Apps → Treatments → Configure.** The specialties the clinic
works with.

Each specialty brings a **reference catalogue**: its treatments and its
plan templates. Enabling it adds that catalogue to the clinic's, and from
there it is the clinic's: names, prices and durations can be changed, own
treatments added, unused ones retired.

## Permissions

- `catalog.read` — see the specialties.
- `catalog.admin` — enable, disable and restore.

## Enabling and disabling

- **Enable** (switch): adds the reference treatments the clinic lacks and
  the specialty's plan templates. It changes nothing the clinic already
  has.
- **Disable**: takes the specialty out of the catalogue. **It deletes
  nothing**: its treatments are deactivated and come back when it is
  enabled again. A treatment that also belongs to another enabled
  specialty stays. Plans and budgets already made do not change.
- **Add N new**: shown when the reference has grown since the clinic
  enabled the specialty. It adds only the missing ones.

Each card says how many reference treatments the clinic has and how many
it has customised.

## Seeing a specialty's treatments

*Treatments*, on each card, unfolds the specialty's reference catalogue
grouped by **sub-areas** — in Orthodontics: diagnosis and planning,
interceptive, fixed appliances, aligners, auxiliaries, follow-up and
retention. Each treatment shows its price (the clinic's if it has one,
otherwise the reference) and, where it applies, a mark:

- **Customised**: the clinic changed its name, price, duration or pricing.
- **Inactive**: it is in the clinic's catalogue, switched off.
- **New**: the reference has it and the clinic does not yet.

Below, *Shared with…* lists the treatments that belong to another
specialty and this one also uses. Sub-areas order the reading; they are
not enabled separately.

## Restoring

*Restore* puts that specialty's reference treatments back to their original
values. Before doing so it shows a warning with the number of customised
treatments that will be overwritten.

- **Lost**: what the clinic changed on the reference treatments — name,
  price, duration, pricing. Deactivated ones are reactivated. The
  specialty's plan templates go back to the reference too.
- **Kept**: treatments the clinic created itself, and plans and budgets
  already made, at the prices they were created with.

## Worth knowing

- Reference prices are a starting point, not a tariff: review them when
  enabling a specialty.
- There is one catalogue per clinic. There are no per-doctor prices.
