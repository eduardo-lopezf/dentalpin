---
module: professionals
screen: list
route: /professionals
related_endpoints:
  - GET /api/v1/professionals
  - GET /api/v1/professionals/{professional_id}
  - POST /api/v1/professionals
  - PUT /api/v1/professionals/{professional_id}
related_permissions:
  - professionals.read
  - professionals.write
related_paths:
  - backend/app/modules/professionals/frontend/pages/professionals/index.vue
  - backend/app/modules/professionals/router.py
last_verified_commit: 0000000
---

# Directory

The directory lists active dentists and collaborators by default. Search by
name, specialty or professional-license number; select a profile type or show
inactive profiles when needed.

## Add or edit a profile

> Creating and editing requires `professionals.write`.

1. Select **Add professional**, or use the pencil on an existing row.
2. Enter name and profile type. Add specialty, professional license, photo URL
   and contact fields as needed.
3. Use **Active** to retain a former collaborator in the directory without
   including them in the default list.
4. Select **Save**.

Profiles are directory records only. They do not grant a login or permissions.
