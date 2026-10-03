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
last_verified_commit: 0d60d45
---

# Directorio

El directorio muestra por defecto los dentistas y colaboradores activos.
Puedes buscar por nombre, especialidad o cédula profesional, filtrar por tipo
de perfil y mostrar también los inactivos.

> **En tablet.** El listado conserva la disposición en filas tanto en
> horizontal como en vertical. Solo los teléfonos lo apilan en tarjetas,
> así que girar la tablet no reorganiza la información.

## Ver un perfil

Selecciona cualquier fila del listado para abrir la **ficha del profesional**:
el retrato en grande, el tipo de perfil, el estado y las especialidades que
ejerce, y debajo un mosaico con la cédula, el correo, el teléfono y si tiene
acceso al sistema. El correo y el teléfono son enlaces: al pulsarlos se abre
el cliente de correo o la marcación.

La ficha responde a la pregunta habitual — quién es esta persona — sin entrar
a modificar nada. Para cambiar los datos, usa **Editar perfil** dentro de la
propia ficha.

## Crear o editar un perfil

> Para crear y editar se requiere `professionals.write`.

1. Selecciona **Añadir profesional**, o abre la ficha de un profesional
   existente y pulsa **Editar perfil**.
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

## Cuenta vinculada

El desplegable **Cuenta vinculada** del formulario dice con qué cuenta entra
esta persona al sistema. Es lo que permite que una anotación clínica diga
**quién responde por ella**: cuando alguien registra una alergia o escribe una
nota, el expediente guarda la cuenta que operó el sistema y, a través de este
vínculo, el profesional y su número de colegiado.

Déjalo en **Sin cuenta** si esa persona no usa el sistema — un colaborador
externo, alguien que aún no tiene acceso. El directorio no exige cuenta, y esa
es la razón por la que el campo puede quedar vacío.

**No se deduce del correo.** El indicador «Usuario con acceso» compara correos
y sirve de pista, nada más: dos personas pueden compartir una dirección
familiar, alguien cambia de correo, una clínica reutiliza uno. La autoría de un
documento clínico no puede apoyarse en una coincidencia, así que el vínculo lo
declaras tú.

La lista solo ofrece cuentas **con acceso a esta clínica**, y no ofrece las que
ya están vinculadas a otro profesional: una cuenta es una persona, y dos fichas
compartiéndola dejarían sin respuesta quién firma cada anotación.

## Especialidad

Cada profesional puede tener **una o varias** especialidades, elegidas del **catálogo
de la clínica** (Ajustes → Catálogo de tratamientos → Por Especialidad), no de
una lista fija. Es el mismo catálogo que clasifica los tratamientos, así que
"Ortodoncia" significa lo mismo en los dos sitios y se puede responder qué
disciplinas cubre la plantilla.

Si el catálogo está vacío, el desplegable sale vacío: primero hay que crear
las especialidades en Ajustes. La búsqueda por especialidad sigue funcionando.
