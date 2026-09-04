---
module: catalog
screen: catalog
route: /settings/catalog
related_endpoints:
  - DELETE /api/v1/catalog/categories/{category_id}
  - DELETE /api/v1/catalog/items/{item_id}
  - DELETE /api/v1/catalog/specialties/{specialty_id}
  - DELETE /api/v1/catalog/vat-types/{vat_type_id}
  - GET /api/v1/catalog/categories
  - GET /api/v1/catalog/categories/{category_id}
  - GET /api/v1/catalog/items
  - GET /api/v1/catalog/items/popular
  - GET /api/v1/catalog/items/search
  - GET /api/v1/catalog/items/{item_id}
  - GET /api/v1/catalog/odontogram-treatments
  - GET /api/v1/catalog/odontogram-treatments/by-category
  - GET /api/v1/catalog/specialties
  - GET /api/v1/catalog/specialties/{specialty_id}
  - GET /api/v1/catalog/specialties/{specialty_id}/items
  - GET /api/v1/catalog/vat-types
  - GET /api/v1/catalog/vat-types/default
  - GET /api/v1/catalog/vat-types/{vat_type_id}
  - POST /api/v1/catalog/categories
  - POST /api/v1/catalog/items
  - POST /api/v1/catalog/specialties
  - POST /api/v1/catalog/vat-types
  - PUT /api/v1/catalog/categories/{category_id}
  - PUT /api/v1/catalog/items/{item_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}
  - PUT /api/v1/catalog/specialties/{specialty_id}/items
  - PUT /api/v1/catalog/vat-types/{vat_type_id}
related_permissions:
  - catalog.read
  - catalog.write
  - catalog.admin
related_paths:
  - backend/app/modules/catalog/frontend/pages/settings/catalog/index.vue
last_verified_commit: 3568519
---

# /settings/catalog

> _Esqueleto generado automáticamente — reemplazar con documentación real cuando se toque este módulo._

_Pantalla `/settings/catalog` del módulo `catalog`._

## Permisos

- `catalog.read`
- `catalog.write`
- `catalog.admin`

## Para qué sirve

_Pendiente de documentar._

## Pestañas

La pantalla tiene dos pestañas:

- **Tipo de Tratamiento**: vista existente, tratamientos agrupados por
  categoría (`TreatmentCategory`).
- **Por Especialidad**: gestión (alta/edición/baja) del catálogo de
  especialidades odontológicas (`Specialty`), independiente de la
  categoría del tratamiento — p. ej. "Cirugía Oral y Maxilofacial",
  y asignación de los tratamientos del catálogo a cada una.

### Asignar tratamientos a una especialidad

Cada especialidad se muestra como un grupo desplegable con los
tratamientos que tiene asignados (código, nombre, categoría y precio).
Un grupo final, **Sin especialidad**, reúne los tratamientos que
todavía no están clasificados, para ver de un vistazo lo que falta.

Con el botón **Asignar tratamientos** (solo administradores) se abre un
listado buscable de todo el catálogo con casillas de selección. Lo que
se guarda es la selección completa: los tratamientos que se desmarcan
pierden la asignación a esa especialidad.

Un tratamiento puede pertenecer a varias especialidades a la vez (una
extracción simple puede ser odontología general y cirugía oral), por lo
que aparecerá en cada uno de los grupos correspondientes.

Los tratamientos inactivos solo aparecen en el listado de asignación si
ya estaban asignados, para poder retirarlos sin reactivarlos.

## Especialidades sembradas

La clínica arranca con diez especialidades base: Odontología General, Higiene
Dental, Endodoncia, Periodoncia, Cirugía Oral y Maxilofacial, Implantología,
Ortodoncia, Odontopediatría, Estética Dental y Rehabilitación Oral. Se pueden
renombrar, desactivar o ampliar (Radiología, Patología Oral, Odontología del
Sueño, ...) sin romper nada: la siembra las reconoce por una clave interna, no
por el nombre visible.

Los tratamientos del catálogo llegan ya clasificados. La asignación parte de la
categoría y se afina por tratamiento donde la categoría se queda corta: la
Implantología reúne el implante (Cirugía), su corona (Restauradora) y la
sobredentadura (Prótesis) — tres categorías, una disciplina. Las carillas son
Restauradora pero además Estética. Los mantenimientos periodontales suman
Higiene Dental.

Volver a sembrar solo rellena huecos: nunca borra las asignaciones que hayas
hecho a mano.

## Paginación

El listado pagina. Hasta ahora el paginador ignoraba los clics —
usaba la API antigua del componente— y solo se veía la primera
página; los tratamientos siguientes existían pero no había forma de
llegar a ellos.

## Editar tratamientos

Los tratamientos que vienen con el sistema son **editables**: precio, nombre,
duración, IVA, categoría, especialidades y fase. También se pueden **desactivar**
si tu clínica no los ofrece, en vez de borrarlos — así el histórico de
presupuestos y facturas que los referencian sigue intacto.

Crear, editar y borrar tratamientos requiere el permiso `catalog.write`, y
gestionar categorías, tipos de IVA y especialidades requiere `catalog.admin`.
**Por defecto solo el perfil administrador tiene ninguno de los dos**, así que
en la práctica es el único que puede modificar el catálogo. Los demás
perfiles ven el catálogo en modo lectura.

El único campo bloqueado en un tratamiento del sistema es el **código interno**:
es la clave por la que la siembra reconoce el tratamiento, y cambiarlo haría que
la siguiente siembra recreara el original como duplicado.

## Columna "Visible"

Cada tratamiento tiene una casilla **Visible** que decide si aparece en el
menú **Tratamientos**. Es la misma casilla en las dos pestañas: si la marcas
en "Tipo de Tratamiento", aparece marcada en "Por Especialidad".

**No confundir con activo/inactivo.** Ocultar un tratamiento solo lo quita de
esa lista de consulta; sigue activo y facturable, y sigue funcionando en
presupuestos, odontograma e histórico. Para dejar de ofrecerlo de verdad,
desactívalo.

Todos los tratamientos nacen visibles. Solo el administrador puede cambiar la
casilla.
