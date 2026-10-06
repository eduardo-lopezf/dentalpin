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

# Configuración de Tratamientos: especialidades

**Configuración → Apps → Tratamientos → Configurar.** Las especialidades
con las que trabaja la clínica.

Cada especialidad trae un **catálogo de referencia**: sus tratamientos y
sus plantillas de plan. Al habilitarla, ese catálogo se añade al de la
clínica, y desde ahí es de la clínica: se pueden cambiar nombres, precios y
duraciones, añadir tratamientos propios o retirar los que no se usen.

## Permisos

- `catalog.read` — ver las especialidades.
- `catalog.admin` — habilitar, deshabilitar y restaurar.

## Habilitar y deshabilitar

- **Habilitar** (interruptor): añade los tratamientos de referencia que la
  clínica no tenga y las plantillas de plan de la especialidad. No cambia
  nada de lo que la clínica ya tiene.
- **Deshabilitar**: saca la especialidad del catálogo. **No borra nada**:
  sus tratamientos se desactivan y vuelven al habilitarla de nuevo. Un
  tratamiento que también pertenece a otra especialidad habilitada se
  queda. Los planes y presupuestos ya hechos no cambian.
- **Añadir N nuevos**: aparece cuando la referencia ha crecido desde que la
  clínica habilitó la especialidad. Añade solo los que faltan.

Cada tarjeta dice cuántos tratamientos de referencia tiene la clínica y
cuántos ha personalizado.

## Ver los tratamientos de una especialidad

*Tratamientos*, en cada tarjeta, despliega el catálogo de referencia de la
especialidad agrupado por **subáreas** — en Ortodoncia: diagnóstico y
planificación, interceptiva, aparatología fija, alineadores, auxiliares,
seguimiento y retención. Cada tratamiento muestra su precio (el de la
clínica si lo tiene, si no el de referencia) y, cuando aplica, una marca:

- **Personalizado**: la clínica cambió su nombre, precio, duración o forma
  de cobro.
- **Inactivo**: está en el catálogo de la clínica, desactivado.
- **Nuevo**: la referencia lo trae y la clínica aún no lo tiene.

Debajo, *Compartidos con…* lista los tratamientos que pertenecen a otra
especialidad y que esta también usa. Las subáreas ordenan la lectura; no
se habilitan por separado.

## Restaurar

*Restaurar* devuelve los tratamientos de referencia de esa especialidad a
sus valores originales. Antes de hacerlo muestra una advertencia con el
número de tratamientos personalizados que se van a sobrescribir.

- **Se pierde**: lo que la clínica cambió en los tratamientos de referencia
  — nombre, precio, duración, forma de cobro. Los que se hubieran
  desactivado se reactivan. Las plantillas de plan de la especialidad
  vuelven también a la referencia.
- **Se conserva**: los tratamientos que la clínica creó por su cuenta, y
  los planes y presupuestos ya hechos, con los precios con los que se
  crearon.

## Lo que conviene saber

- Los precios de referencia son un punto de partida, no una tarifa:
  conviene revisarlos al habilitar una especialidad.
- El catálogo es uno por clínica. No hay precios distintos por doctor.
