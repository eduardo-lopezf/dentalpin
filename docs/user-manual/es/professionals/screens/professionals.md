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

# Directorio

El directorio muestra por defecto los dentistas y colaboradores activos.
Puedes buscar por nombre, especialidad o cédula profesional, filtrar por tipo
de perfil y mostrar también los inactivos.

## Crear o editar un perfil

> Para crear y editar se requiere `professionals.write`.

1. Selecciona **Añadir profesional** o el lápiz de una fila existente.
2. Indica nombre y tipo de perfil. Completa especialidad, cédula, URL de la
   foto y datos de contacto según corresponda.
3. Usa **Activo** para conservar un colaborador que ya no ejerce en la clínica
   sin que aparezca en el listado habitual.
4. Selecciona **Guardar**.

Los perfiles son registros del directorio; no crean cuentas de acceso ni
otorgan permisos.
