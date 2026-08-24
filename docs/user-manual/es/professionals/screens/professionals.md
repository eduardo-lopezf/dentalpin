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
last_verified_commit: e2b7328
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
4. Si el correo electrónico del perfil coincide con el de un usuario con
   acceso a esta clínica, junto a **Activo** aparece la leyenda de solo
   lectura **"Usuario con acceso"** con una palomita verde.
5. Selecciona **Guardar**.

Los perfiles son registros del directorio; no crean cuentas de acceso ni
otorgan permisos. El indicador "Usuario con acceso" solo informa si ya
existe una cuenta con ese correo — no la crea ni la vincula.

## Especialidad

Cada profesional puede tener **una o varias** especialidades, elegidas del **catálogo
de la clínica** (Ajustes → Catálogo de tratamientos → Por Especialidad), no de
una lista fija. Es el mismo catálogo que clasifica los tratamientos, así que
"Ortodoncia" significa lo mismo en los dos sitios y se puede responder qué
disciplinas cubre la plantilla.

Si el catálogo está vacío, el desplegable sale vacío: primero hay que crear
las especialidades en Ajustes. La búsqueda por especialidad sigue funcionando.
