---
module: professionals
last_verified_commit: 0000000
---

# Professionals — permissions

| Permission | Allows | Required by |
|------------|--------|-------------|
| `professionals.read` | View the professionals directory and a profile. | `GET /api/v1/professionals`, `GET /api/v1/professionals/{professional_id}` |
| `professionals.write` | Create and edit profiles, including active status. | `POST /api/v1/professionals`, `PUT /api/v1/professionals/{professional_id}` |

By default admins have both permissions; dentists, hygienists, assistants and
receptionists receive read access. Permissions are declared relative to the
module in `ProfessionalsModule.get_permissions()` and namespaced by the
registry.
